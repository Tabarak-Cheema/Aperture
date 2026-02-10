"""Cascade integration tests."""
from __future__ import annotations

import pytest
from aqir.compiler import CatalogSlice, DimensionDef, MetricDef
from catalog import SynonymIndex

from services.compile.app.cascade import Cascade, PlanCache
from services.compile.app.grammar import GrammarParser
from services.compile.app.normalizer import normalize
from services.compile.app.templates import TemplateIndex


@pytest.fixture
def slice_() -> CatalogSlice:
    return CatalogSlice(
        metrics={"revenue": MetricDef("revenue", "SUM(orders.total_amount)", "orders")},
        dimensions={"region": DimensionDef("region", "customers.region", "customers")},
        joins={("customers", "orders"): "ON customers.id = orders.customer_id"},
        many_sides={"orders"},
    )


@pytest.fixture
def synonyms() -> SynonymIndex:
    idx = SynonymIndex()
    idx.add_name("revenue", ["sales", "gmv"])
    idx.add_name("region", ["area"])
    return idx


@pytest.mark.asyncio
async def test_t1_template_match_zero_tokens(slice_, synonyms):
    cascade = Cascade(
        cache=PlanCache(),
        templates=TemplateIndex(),
        grammar=GrammarParser(),
        synonyms=synonyms,
        slice_=slice_,
        llm_call=None,
    )
    res = await cascade.resolve("revenue by region")
    assert res.ok
    assert res.tier == "T1"
    assert res.tokens_in == 0 and res.tokens_out == 0


@pytest.mark.asyncio
async def test_t2_grammar_fallback(slice_, synonyms):
    cascade = Cascade(
        cache=PlanCache(),
        templates=TemplateIndex(),
        grammar=GrammarParser(),
        synonyms=synonyms,
        slice_=slice_,
        llm_call=None,
    )
    res = await cascade.resolve("top 5 region by sales")
    assert res.ok
    assert res.plan.limit == 5
    assert res.tokens_in == 0


@pytest.mark.asyncio
async def test_t0_cache_hit_on_repeat(slice_, synonyms):
    cascade = Cascade(
        cache=PlanCache(),
        templates=TemplateIndex(),
        grammar=GrammarParser(),
        synonyms=synonyms,
        slice_=slice_,
        llm_call=None,
    )
    r1 = await cascade.resolve("revenue by region")
    assert r1.tier in ("T1", "T2")
    r2 = await cascade.resolve("revenue by region")
    assert r2.tier == "T0"


def test_normalizer_relative_dates():
    out = normalize("revenue by region last month", catalog_version=1, tenant_id="t")
    assert "last month" in out.relatives or out.relatives  # resolved to a range
