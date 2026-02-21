"""Insight diffing.

On every data refresh, compare the new metric value with the previous version.
Report deltas only if they are large relative to the historical standard
deviation — so normal noise isn't surfaced.

See §3.1 of the transformation plan. Zero model tokens by default; an optional
"write it up" button sends ~150 tokens of precomputed facts to the LLM.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import mean, pstdev


@dataclass(slots=True)
class MetricDelta:
    metric: str
    previous: float
    current: float
    abs_change: float
    pct_change: float
    z_score: float
    significant: bool


def diff_metric(
    *, metric: str, history: list[float], current: float, min_z: float = 1.5,
) -> MetricDelta | None:
    """Return a :class:`MetricDelta` when the change is statistically significant."""
    if not history:
        return None
    previous = history[-1]
    abs_change = current - previous
    pct_change = (abs_change / previous) if previous else math.inf
    mu = mean(history)
    sigma = pstdev(history) or 1e-9
    z = (current - mu) / sigma
    return MetricDelta(
        metric=metric,
        previous=previous,
        current=current,
        abs_change=abs_change,
        pct_change=pct_change,
        z_score=z,
        significant=abs(z) >= min_z,
    )


@dataclass(slots=True)
class Driver:
    dimension_value: str
    contribution: float            # absolute contribution to the metric delta
    contribution_share: float      # share of the total delta explained


def decompose_drivers(
    *, previous_by_dim: dict[str, float], current_by_dim: dict[str, float],
) -> list[Driver]:
    """Additive contribution analysis down one level of the dimension tree.

    For each dimension value, the contribution is ``current - previous`` on
    that slice. Sorted by absolute contribution, descending.
    """
    keys = set(previous_by_dim) | set(current_by_dim)
    deltas: list[tuple[str, float]] = []
    for k in keys:
        d = current_by_dim.get(k, 0.0) - previous_by_dim.get(k, 0.0)
        deltas.append((k, d))

    total = sum(d for _, d in deltas) or 1e-9
    deltas.sort(key=lambda x: abs(x[1]), reverse=True)
    return [
        Driver(dimension_value=k, contribution=d, contribution_share=d / total)
        for k, d in deltas
    ]


def narrate_delta(delta: MetricDelta, drivers: list[Driver], top_k: int = 3) -> str:
    """Deterministic plain-English narration. 0 tokens.

    Example output:
        "Revenue fell 12% (z=-2.1). 9 points came from North; 7 of those from product X."
    """
    direction = "rose" if delta.abs_change > 0 else "fell"
    headline = f"{delta.metric} {direction} {abs(delta.pct_change):.1%} (z={delta.z_score:.1f})."
    if not drivers:
        return headline
    parts = []
    for d in drivers[:top_k]:
        parts.append(f"{abs(d.contribution_share):.0%} from {d.dimension_value}")
    return headline + " " + "; ".join(parts) + "."
