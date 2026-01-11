"""Tests for the AQIR compiler."""
from __future__ import annotations

import pytest
from aqir import AQIRPlan, compile_plan, validate_plan
from aqir.compiler import CatalogSlice, DimensionDef, MetricDef
from aqir.validator import ValidationError, render_plan_english


@pytest.fixture
def catalog() -> CatalogSlice:
    return CatalogSlice(
        metrics={
            "revenue": MetricDef("revenue", "SUM(orders.total_amount)", "orders", "number"),
            "order_count": MetricDef("order_count", "COUNT(DISTINCT orders.id)", "orders", "number"),
        },
        dimensions={
            "region": DimensionDef("region", "customers.region", "customers", "string"),
            "country": DimensionDef("country", "customers.country", "customers", "string"),
        },
        joins={("customers", "orders"): "ON customers.id = orders.customer_id"},
        many_sides={"orders"},
    )


def test_compile_basic_aggregation(catalog):
    plan = AQIRPlan(
        metrics=["revenue"],
        dimensions=["region"],
        filters=[{"dim": "country", "op": "=", "value": "PK"}],
        sort=[{"by": "revenue", "dir": "desc"}],
        limit=10,
    )
    sql = compile_plan(plan, catalog, dialect="duckdb")
    assert "SELECT" in sql.upper()
    assert "GROUP BY" in sql.upper()
    assert "ORDER BY" in sql.upper()
    assert "LIMIT 10" in sql.upper()


def test_time_grain_is_emitted(catalog):
    plan = AQIRPlan(
        metrics=["revenue"],
        time={"dim": "orders.order_date", "range": "last_quarter", "grain": "month"},
    )
    sql = compile_plan(plan, catalog, dialect="duckdb")
    assert "DATE_TRUNC" in sql.upper()
    assert "MONTH" in sql.upper()


def test_select_only(catalog):
    """The compiler never emits anything other than a SELECT."""
    plan = AQIRPlan(metrics=["revenue"])
    sql = compile_plan(plan, catalog, dialect="duckdb")
    upper = sql.upper().strip()
    for stmt in ("DROP", "DELETE", "UPDATE", "INSERT", "TRUNCATE", "ALTER", "CREATE"):
        assert stmt not in upper


def test_fanout_safe(catalog):
    """A metric on the many side gets pre-aggregated."""
    plan = AQIRPlan(metrics=["revenue"], dimensions=["region"])
    sql = compile_plan(plan, catalog, dialect="duckdb")
    assert "WITH" in sql.upper()  # the pre-agg CTE


def test_validator_rejects_unknown_metric(catalog):
    plan = AQIRPlan(metrics=["gmv"])
    with pytest.raises(ValidationError):
        validate_plan(plan, catalog)


def test_validator_rejects_incompat_filter(catalog):
    plan = AQIRPlan(
        metrics=["revenue"],
        filters=[{"dim": "region", "op": "=", "value": 42}],  # region is string
    )
    with pytest.raises(ValidationError):
        validate_plan(plan, catalog)


def test_plan_fingerprint_is_stable(catalog):
    p1 = AQIRPlan(metrics=["revenue"], dimensions=["region"], limit=10)
    p2 = AQIRPlan(limit=10, metrics=["revenue"], dimensions=["region"])
    assert p1.fingerprint() == p2.fingerprint()


def test_english_rendering(catalog):
    plan = AQIRPlan(
        metrics=["revenue"],
        dimensions=["region"],
        time={"dim": "orders.order_date", "range": "last_quarter", "grain": "month"},
        limit=10,
    )
    s = render_plan_english(plan)
    assert "revenue" in s
    assert "region" in s
    assert "month" in s
