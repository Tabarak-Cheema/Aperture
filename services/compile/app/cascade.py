"""The resolution cascade: T0 → T5.

Every question falls through the tiers and stops at the first that resolves it
with high confidence. Only T4 and T5 ever call the model; everything else is
0 tokens.

* T0 plan cache
* T1 template match + entity linker
* T2 analytic grammar (deterministic parser for the 40–60 BI phrasings)
* T3 local small model via llama.cpp (optional, not wired in this build)
* T4 cloud LLM via :mod:`llm_gateway`
* T5 targeted repair (one retry with just the error + failing fragment)
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from aqir import AQIRPlan, ValidationError, validate_plan
from aqir.compiler import CatalogSlice
from aqir.jsonschema import json_schema
from aqir.validator import render_plan_english
from catalog import SynonymIndex

from .grammar import GrammarParser
from .normalizer import Normalized, normalize
from .templates import TemplateIndex


@dataclass(slots=True)
class CascadeResult:
    plan: AQIRPlan | None
    tier: str
    tokens_in: int = 0
    tokens_out: int = 0
    note: str = ""
    english: str = ""

    @property
    def ok(self) -> bool:
        return self.plan is not None


@dataclass(slots=True)
class PlanCache:
    """T0 — normalized question + catalog version -> plan (0 tokens)."""

    _store: dict[str, AQIRPlan] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self._store is None:
            self._store = {}

    def get(self, fingerprint: str) -> AQIRPlan | None:
        return self._store.get(fingerprint)

    def put(self, fingerprint: str, plan: AQIRPlan) -> None:
        self._store[fingerprint] = plan


@dataclass
class Cascade:
    """Runs a question through T0–T5.

    The LLM client is optional at construction so the gateway can be injected
    (and mocked in tests).
    """

    cache: PlanCache
    templates: TemplateIndex
    grammar: GrammarParser
    synonyms: SynonymIndex
    slice_: CatalogSlice
    tenant_id: str = "default"
    catalog_version: int = 1
    llm_call: Any | None = None  # callable: (system, user, schema) -> GatewayCall
    confidence_threshold: float = 0.8

    async def resolve(self, question: str) -> CascadeResult:
        norm = normalize(question, self.catalog_version, self.tenant_id)

        # T0 — plan cache
        cached = self.cache.get(norm.fingerprint)
        if cached is not None:
            return CascadeResult(plan=cached, tier="T0", english=render_plan_english(cached))

        # T1 — template match
        hit = self.templates.best(norm.text, self.synonyms)
        if hit is not None and hit.confidence >= self.confidence_threshold:
            plan = hit.plan
            try:
                validate_plan(plan, self.slice_)
            except ValidationError:
                plan = None
            if plan is not None:
                self._promote(norm, plan)
                return CascadeResult(plan=plan, tier="T1", english=render_plan_english(plan))

        # T2 — analytic grammar
        try:
            plan = self.grammar.parse(norm.text, self.synonyms)
        except ValueError:
            plan = None
        if plan is not None:
            try:
                validate_plan(plan, self.slice_)
                self._promote(norm, plan)
                return CascadeResult(plan=plan, tier="T2", english=render_plan_english(plan))
            except ValidationError:
                pass

        # T3 — local model: not wired. Fall through.

        # T4 — cloud LLM
        if self.llm_call is None:
            return CascadeResult(plan=None, tier="T4", note="no LLM configured")

        schema = json_schema()
        slice_text = self._render_slice_text()
        examples = self.templates.top_examples(3)
        call = await self.llm_call(question=question, slice_text=slice_text, examples=examples, schema=schema)
        if not call.ok:
            return CascadeResult(
                plan=None, tier="T4",
                tokens_in=call.input_tokens, tokens_out=call.output_tokens,
                note=call.error or "LLM error",
            )
        try:
            data = json.loads(call.content)
            plan = AQIRPlan.model_validate(data)
            validate_plan(plan, self.slice_)
        except Exception as exc:
            # T5 — targeted repair: send back just the error
            repair = await self.llm_call(
                question=question + f"\n\nREPAIR: {exc}\nFailing output: {call.content}",
                slice_text=slice_text,
                examples=examples,
                schema=schema,
            )
            if not repair.ok:
                return CascadeResult(
                    plan=None, tier="T5",
                    tokens_in=call.input_tokens + repair.input_tokens,
                    tokens_out=call.output_tokens + repair.output_tokens,
                    note=repair.error or "repair failed",
                )
            try:
                plan = AQIRPlan.model_validate(json.loads(repair.content))
                validate_plan(plan, self.slice_)
            except Exception as exc2:
                return CascadeResult(
                    plan=None, tier="T5",
                    tokens_in=call.input_tokens + repair.input_tokens,
                    tokens_out=call.output_tokens + repair.output_tokens,
                    note=f"repair rejected: {exc2}",
                )
            self._promote(norm, plan)
            return CascadeResult(
                plan=plan, tier="T5",
                tokens_in=call.input_tokens + repair.input_tokens,
                tokens_out=call.output_tokens + repair.output_tokens,
                english=render_plan_english(plan),
            )

        self._promote(norm, plan)
        return CascadeResult(
            plan=plan, tier="T4",
            tokens_in=call.input_tokens, tokens_out=call.output_tokens,
            english=render_plan_english(plan),
        )

    def _promote(self, norm: Normalized, plan: AQIRPlan) -> None:
        self.cache.put(norm.fingerprint, plan)
        self.templates.add_example(norm.text, plan)

    def _render_slice_text(self) -> str:
        """Compressed sketch of the slice for the LLM prompt."""
        lines = []
        for name, m in self.slice_.metrics.items():
            lines.append(f"metric {name}: {m.expr} ({m.type})")
        for name, d in self.slice_.dimensions.items():
            lines.append(f"dim {name}: {d.expr} ({d.type})")
        return "\n".join(lines)
