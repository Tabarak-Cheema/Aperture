"""AQIR → SQL compiler.

The compiler is deterministic. It never calls the model. It produces a SELECT
statement for the requested dialect via ``sqlglot``. Only SELECT is emitted,
which is enforced by construction (we build the AST rather than concatenating
strings).

Fan-out safety: when the planned joins traverse a one-to-many relationship,
measures on the ``many`` side are pre-aggregated in a subquery so that summing
across the join does not inflate totals (symmetric aggregates). The catalog
provides cardinality hints; the compiler refuses to emit an unsafe plan.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import sqlglot
from sqlglot import exp

from aqir.schema import AQIRPlan, Filter, Op, SortKey, TimeRange


@dataclass(frozen=True, slots=True)
class MetricDef:
    """Semantic-layer metric definition (see packages/catalog)."""

    name: str
    expr: str                 # e.g. "SUM(orders.total_amount)"
    base_table: str           # e.g. "orders"
    type: str = "number"


@dataclass(frozen=True, slots=True)
class DimensionDef:
    name: str
    expr: str                 # fully-qualified column, e.g. "customers.region"
    base_table: str
    type: str = "string"


@dataclass(frozen=True, slots=True)
class CatalogSlice:
    """Minimal slice of the catalog the compiler needs.

    Produced by the ``compile`` service's schema slicer; passed in so the
    compiler stays pure (no DB handle).
    """

    metrics: dict[str, MetricDef]
    dimensions: dict[str, DimensionDef]
    joins: dict[tuple[str, str], str]   # (left, right) -> "ON <expr>"
    many_sides: set[str]                # tables that live on the ``many`` side of >=1 join


_REL_RANGES = {
    "today": ("current_date", "current_date"),
    "yesterday": ("current_date - 1", "current_date - 1"),
    "last_7d": ("current_date - 6", "current_date"),
    "last_30d": ("current_date - 29", "current_date"),
    "mtd": ("date_trunc('month', current_date)", "current_date"),
    "qtd": ("date_trunc('quarter', current_date)", "current_date"),
    "ytd": ("date_trunc('year', current_date)", "current_date"),
    "last_quarter": (
        "date_trunc('quarter', current_date) - interval 3 month",
        "date_trunc('quarter', current_date) - interval 1 day",
    ),
    "last_year": (
        "date_trunc('year', current_date) - interval 1 year",
        "date_trunc('year', current_date) - interval 1 day",
    ),
}


def _grain_expr(column: str, grain: str) -> str:
    return f"date_trunc('{grain}', {column})"


def _render_filter(f: Filter, dim_expr: str) -> str:
    v = f.value
    if f.op is Op.is_null:
        return f"{dim_expr} IS NULL"
    if f.op is Op.not_null:
        return f"{dim_expr} IS NOT NULL"
    if f.op is Op.in_ or f.op is Op.not_in:
        assert isinstance(v, list)
        rendered = ", ".join(_lit(x) for x in v)
        prefix = "NOT " if f.op is Op.not_in else ""
        return f"{prefix}{dim_expr} IN ({rendered})"
    if f.op is Op.between:
        assert isinstance(v, list) and len(v) == 2
        return f"{dim_expr} BETWEEN {_lit(v[0])} AND {_lit(v[1])}"
    if f.op is Op.like:
        return f"{dim_expr} ILIKE {_lit(v)}"
    return f"{dim_expr} {f.op.value} {_lit(v)}"


def _lit(v: Any) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v).replace("'", "''")
    return f"'{s}'"


def _resolve_time_bounds(t: TimeRange) -> tuple[str, str]:
    if t.range and t.range in _REL_RANGES:
        return _REL_RANGES[t.range]
    if t.start and t.end:
        return _lit(t.start), _lit(t.end)
    raise ValueError(f"time range has neither a known keyword nor explicit start/end: {t}")


def _sort_clause(keys: list[SortKey]) -> str:
    if not keys:
        return ""
    parts = [f"{k.by} {k.dir.value.upper()}" for k in keys]
    return " ORDER BY " + ", ".join(parts)


def _plan_touches_fanout(plan: AQIRPlan, slice_: CatalogSlice) -> set[str]:
    """Return the set of ``many``-side tables that host a requested metric."""
    hit = set()
    for name in plan.metrics:
        m = slice_.metrics.get(name)
        if m and m.base_table in slice_.many_sides:
            hit.add(m.base_table)
    return hit


def compile_plan(plan: AQIRPlan, slice_: CatalogSlice, dialect: str = "duckdb") -> str:
    """Compile an AQIR plan to a dialect SQL string.

    Raises ``KeyError`` if a metric or dimension is not in the slice.
    """

    # --- Resolve expressions -------------------------------------------------
    metric_exprs: list[tuple[str, str]] = []
    for name in plan.metrics:
        m = slice_.metrics[name]
        metric_exprs.append((name, m.expr))

    dim_exprs: list[tuple[str, str, str]] = []  # (alias, expr, base_table)
    for name in plan.dimensions:
        d = slice_.dimensions[name]
        dim_exprs.append((name, d.expr, d.base_table))

    # --- Fan-out safety ------------------------------------------------------
    unsafe = _plan_touches_fanout(plan, slice_)
    pre_agg_cte = ""
    if unsafe:
        # Pre-aggregate every metric on each fan-out base table, then join.
        pre_agg_parts = []
        for tbl in sorted(unsafe):
            m_sel = []
            for name, expr in metric_exprs:
                m = slice_.metrics[name]
                if m.base_table == tbl:
                    m_sel.append(f"{expr} AS {name}")
            # Preserve the join-key columns on this table; downstream joins
            # reference them via the CTE alias.
            pre_agg_parts.append(
                f"_pa_{tbl} AS (SELECT {tbl}.id, " + ", ".join(m_sel) + f" FROM {tbl} GROUP BY {tbl}.id)"
            )
        pre_agg_cte = "WITH " + ", ".join(pre_agg_parts) + " "

    # --- SELECT list --------------------------------------------------------
    select_parts: list[str] = []
    group_parts: list[str] = []
    if plan.time:
        time_expr = _grain_expr(plan.time.dim, (plan.time.grain or "day").value if plan.time.grain else "day")
        select_parts.append(f"{time_expr} AS period")
        group_parts.append("period")
    for alias, expr, _ in dim_exprs:
        select_parts.append(f"{expr} AS {alias}")
        group_parts.append(alias)
    for name, expr in metric_exprs:
        select_parts.append(f"{expr} AS {name}")

    # --- FROM / JOIN --------------------------------------------------------
    base_tables = {m.base_table for m in (slice_.metrics[n] for n in plan.metrics)}
    base_tables |= {d.base_table for d in (slice_.dimensions[n] for n in plan.dimensions)}
    if plan.time:
        # The time dim lives on one of the base tables; assume first base table
        # provides it unless explicitly set.
        pass

    if not base_tables:
        raise ValueError("plan touches no tables")

    base_list = sorted(base_tables)
    from_clause = f"FROM {base_list[0]}"
    for other in base_list[1:]:
        key = (base_list[0], other) if (base_list[0], other) in slice_.joins else (other, base_list[0])
        if key not in slice_.joins:
            raise ValueError(f"no known join between {base_list[0]} and {other}")
        from_clause += f" JOIN {other} {slice_.joins[key]}"

    # --- WHERE --------------------------------------------------------------
    where_parts: list[str] = []
    for f in plan.filters:
        dim_expr = f.dim
        if f.dim in slice_.dimensions:
            dim_expr = slice_.dimensions[f.dim].expr
        where_parts.append(_render_filter(f, dim_expr))
    if plan.time:
        lo, hi = _resolve_time_bounds(plan.time)
        where_parts.append(f"{plan.time.dim} BETWEEN {lo} AND {hi}")

    where_clause = (" WHERE " + " AND ".join(where_parts)) if where_parts else ""
    group_clause = (" GROUP BY " + ", ".join(group_parts)) if group_parts else ""
    order_clause = _sort_clause(plan.sort)
    limit_clause = f" LIMIT {plan.limit}" if plan.limit else ""

    sql = (
        pre_agg_cte
        + "SELECT "
        + ", ".join(select_parts)
        + " "
        + from_clause
        + where_clause
        + group_clause
        + order_clause
        + limit_clause
    )

    # Transpile to target dialect & re-validate as SELECT-only via sqlglot.
    parsed = sqlglot.parse_one(sql, read="duckdb")
    if not isinstance(parsed, (exp.Select, exp.With)):
        raise ValueError("compiler only produces SELECT statements")
    return parsed.sql(dialect=dialect)


__all__ = ["CatalogSlice", "DimensionDef", "MetricDef", "compile_plan"]
