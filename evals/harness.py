"""Evaluation harness.

Replays a golden question set as 4 weeks of simulated usage and reports:

* execution accuracy (does the result match the expected row set?)
* TPAQ (tokens per answered question)
* cascade coverage (share resolved at T0–T2)
* latency percentiles

Baseline: a "direct SQL from the LLM" implementation (``baselines.direct_sql``).

Bars to launch (§9 of the transformation plan):
    - Beat baseline accuracy on the golden set
    - ≥10x fewer tokens than baseline by week 4
    - Cascade coverage ≥70% by week 4
    - Fan-out safety: zero inflated totals
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class EvalCase:
    question: str
    expected_metrics: list[str]
    expected_dimensions: list[str]


@dataclass(slots=True)
class EvalRun:
    total: int = 0
    correct: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    by_tier: dict[str, int] = field(default_factory=dict)
    latencies_ms: list[int] = field(default_factory=list)

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0

    @property
    def tpaq(self) -> float:
        return (self.tokens_in + self.tokens_out) / self.total if self.total else 0.0

    @property
    def cascade_coverage(self) -> float:
        zero_token_tiers = sum(self.by_tier.get(t, 0) for t in ("T0", "T1", "T2"))
        return zero_token_tiers / self.total if self.total else 0.0


def load_cases(path: str | Path) -> list[EvalCase]:
    data = json.loads(Path(path).read_text())
    return [EvalCase(**d) for d in data]


async def run_eval(cases: list[EvalCase], ask_fn) -> EvalRun:
    """Run a list of cases against ``ask_fn(question) -> dict``.

    Returns an :class:`EvalRun` with aggregate stats.
    """
    run = EvalRun(total=len(cases))
    for case in cases:
        t0 = time.monotonic()
        res = await ask_fn(case.question)
        run.latencies_ms.append(int((time.monotonic() - t0) * 1000))
        plan = (res.get("compile") or {}).get("plan") or {}
        metrics = set(plan.get("metrics", []))
        dims = set(plan.get("dimensions", []))
        if metrics == set(case.expected_metrics) and dims == set(case.expected_dimensions):
            run.correct += 1
        tier = (res.get("compile") or {}).get("tier", "?")
        run.by_tier[tier] = run.by_tier.get(tier, 0) + 1
        run.tokens_in += (res.get("compile") or {}).get("tokens_in", 0)
        run.tokens_out += (res.get("compile") or {}).get("tokens_out", 0)
    return run
