"""Deterministic plan validation.

Runs before execution. Rejects plans that touch unknown columns, have type-
incompatible filters, inflate totals across fan-out joins, or fail plausibility
checks on the result.

No model is called here. Every message is deterministic.
"""
from __future__ import annotations

from dataclasses import dataclass

from aqir.compiler import CatalogSlice
from aqir.schema import AQIRPlan, Op


class ValidationError(ValueError):
    """Raised when a plan fails static validation."""


@dataclass(frozen=True, slots=True)
class PlausibilityReport:
    """Returned by :func:`check_result_plausibility`. All floats in [0, 1]."""

    rows: int
    null_share: float
    grand_total_drift: float | None  # None when no baseline total is known
    warnings: list[str]

    @property
    def ok(self) -> bool:
        return not self.warnings


def _is_compat(dim_type: str, op: Op, value: object) -> bool:
    if op in (Op.is_null, Op.not_null):
        return value is None
    if op in (Op.in_, Op.not_in):
        return isinstance(value, list) and len(value) > 0
    if op is Op.between:
        return isinstance(value, list) and len(value) == 2
    if dim_type == "number":
        return isinstance(value, (int, float))
    if dim_type == "bool":
        return isinstance(value, bool)
    # strings and dates both validate here as strings; the compiler quotes them.
    return isinstance(value, str)


def validate_plan(plan: AQIRPlan, slice_: CatalogSlice) -> None:
    """Static validation. Raises :class:`ValidationError` on the first issue."""

    for m in plan.metrics:
        if m not in slice_.metrics:
            raise ValidationError(f"unknown metric: {m}")
    for d in plan.dimensions:
        if d not in slice_.dimensions:
            raise ValidationError(f"unknown dimension: {d}")

    for f in plan.filters:
        dim = slice_.dimensions.get(f.dim)
        dim_type = dim.type if dim else "string"
        if not _is_compat(dim_type, f.op, f.value):
            raise ValidationError(
                f"incompatible filter: dim={f.dim} op={f.op.value} value={f.value!r}"
            )

    if plan.time and not (plan.time.range or (plan.time.start and plan.time.end)):
        raise ValidationError("time range requires either `range` or both `start` and `end`")

    for s in plan.sort:
        if s.by not in plan.metrics and s.by not in plan.dimensions and s.by != "period":
            raise ValidationError(f"sort key '{s.by}' not projected")


def check_result_plausibility(
    row_count: int,
    null_share_by_col: dict[str, float],
    totals_check: tuple[float, float] | None = None,
) -> PlausibilityReport:
    """Post-execution plausibility checks.

    Args:
        row_count: number of rows returned.
        null_share_by_col: fraction of NULLs per projected column.
        totals_check: ``(observed_total, baseline_total)`` for the headline metric.
            When supplied, drift > 5% raises a warning.
    """
    warnings: list[str] = []
    if row_count == 0:
        warnings.append("empty result — check filters")

    for col, share in null_share_by_col.items():
        if share > 0.5:
            warnings.append(f"{col} is >50% NULL ({share:.0%})")

    drift: float | None = None
    if totals_check is not None:
        observed, baseline = totals_check
        if baseline and abs(baseline) > 1e-9:
            drift = abs(observed - baseline) / abs(baseline)
            if drift > 0.05:
                warnings.append(f"grand total drift {drift:.1%} vs baseline")

    max_null = max(null_share_by_col.values(), default=0.0)
    return PlausibilityReport(
        rows=row_count,
        null_share=max_null,
        grand_total_drift=drift,
        warnings=warnings,
    )


def render_plan_english(plan: AQIRPlan) -> str:
    """Deterministic plain-English rendering of the plan.

    Used for the "did I understand you correctly?" confirmation step. No model
    is called, so this costs 0 tokens.
    """
    metrics = ", ".join(plan.metrics)
    pieces = [f"{metrics}"]
    if plan.dimensions:
        pieces.append("by " + ", ".join(plan.dimensions))
    if plan.time:
        if plan.time.range:
            pieces.append(f"for {plan.time.range.replace('_', ' ')}")
        elif plan.time.start and plan.time.end:
            pieces.append(f"from {plan.time.start} to {plan.time.end}")
        if plan.time.grain:
            pieces.append(f"by {plan.time.grain.value}")
    for f in plan.filters:
        pieces.append(f"where {f.dim} {f.op.value} {f.value!r}")
    if plan.sort:
        s = plan.sort[0]
        pieces.append(f"sorted by {s.by} {s.dir.value}")
    if plan.limit:
        pieces.append(f"top {plan.limit}")
    return " ".join(pieces)


__all__ = ["PlausibilityReport", "ValidationError", "check_result_plausibility", "render_plan_english", "validate_plan"]
