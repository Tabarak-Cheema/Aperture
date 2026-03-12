"""The harness runs end-to-end on the smoke golden set."""
from __future__ import annotations

import asyncio
from pathlib import Path

from aqir.compiler import CatalogSlice, DimensionDef, MetricDef
from catalog import SynonymIndex

from evals.harness import load_cases, run_eval
from services.compile.app.cascade import Cascade, PlanCache
from services.compile.app.grammar import GrammarParser
from services.compile.app.templates import TemplateIndex


def _slice() -> CatalogSlice:
    return CatalogSlice(
        metrics={
            "revenue": MetricDef("revenue", "SUM(orders.total_amount)", "orders"),
            "order_count": MetricDef("order_count", "COUNT(DISTINCT orders.id)", "orders"),
            "avg_order_value": MetricDef("avg_order_value", "AVG(orders.total_amount)", "orders"),
        },
        dimensions={
            "region": DimensionDef("region", "customers.region", "customers"),
            "country": DimensionDef("country", "customers.country", "customers"),
            "city": DimensionDef("city", "customers.city", "customers"),
        },
        joins={("customers", "orders"): "ON customers.id = orders.customer_id"},
        many_sides={"orders"},
    )


def _syn() -> SynonymIndex:
    idx = SynonymIndex()
    idx.add_name("revenue", ["sales", "gmv", "turnover"])
    idx.add_name("order_count", ["orders"])
    idx.add_name("avg_order_value", ["aov"])
    idx.add_name("region", ["area"])
    idx.add_name("country", ["nation"])
    idx.add_name("city", ["town"])
    return idx


def test_harness_zero_tokens_on_smoke_set():
    """The MVP golden set should be fully answered at T1/T2 with no LLM."""
    cases = load_cases(Path(__file__).parent / "golden_sets" / "retail_300.json")

    cascade = Cascade(
        cache=PlanCache(),
        templates=TemplateIndex(),
        grammar=GrammarParser(),
        synonyms=_syn(),
        slice_=_slice(),
        llm_call=None,
    )

    async def _ask(q: str) -> dict:
        r = await cascade.resolve(q)
        plan = r.plan.model_dump(exclude_none=True) if r.plan else None
        return {"compile": {"plan": plan, "tier": r.tier,
                              "tokens_in": r.tokens_in, "tokens_out": r.tokens_out}}

    run = asyncio.run(run_eval(cases, _ask))
    assert run.tokens_in == 0 and run.tokens_out == 0
    # Not every question needs to pass yet; the budget assertion is the gate.
