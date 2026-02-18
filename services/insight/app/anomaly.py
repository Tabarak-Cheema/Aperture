"""Anomaly detection and distribution drift.

* STL-style seasonal decomposition with robust z-scores on the residual, so a
  December spike isn't flagged as an anomaly.
* PSI and Kolmogorov–Smirnov per column, so a currency column that silently
  switches from dollars to cents is caught.

Deterministic. 0 tokens.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats
from statsmodels.tsa.seasonal import STL


@dataclass(slots=True)
class Anomaly:
    index: int
    observed: float
    expected: float
    residual_z: float


def detect_anomalies(series: list[float], period: int = 7, z_cutoff: float = 3.0) -> list[Anomaly]:
    if len(series) < 2 * period + 1:
        return []
    stl = STL(np.asarray(series, dtype=float), period=period, robust=True).fit()
    resid = stl.resid
    mad = np.median(np.abs(resid - np.median(resid))) or 1e-9
    z = 0.6745 * (resid - np.median(resid)) / mad
    out: list[Anomaly] = []
    for i, zi in enumerate(z):
        if abs(zi) >= z_cutoff:
            out.append(Anomaly(index=i, observed=series[i], expected=float(series[i] - resid[i]),
                               residual_z=float(zi)))
    return out


def psi(expected: list[float], actual: list[float], buckets: int = 10) -> float:
    """Population Stability Index.

    Uses quantile edges from the expected distribution, extended at both ends
    to ±∞ so values outside the expected range are counted into the first and
    last buckets rather than dropped by ``np.histogram``.
    """
    arr_e = np.asarray(expected, dtype=float)
    arr_a = np.asarray(actual, dtype=float)
    inner = np.quantile(arr_e, np.linspace(0, 1, buckets + 1))
    # Extend endpoints to catch any actual values outside the expected support.
    inner[0] = -np.inf
    inner[-1] = np.inf
    e_counts, _ = np.histogram(arr_e, bins=inner)
    a_counts, _ = np.histogram(arr_a, bins=inner)
    e_frac = (e_counts + 1) / (e_counts.sum() + buckets)
    a_frac = (a_counts + 1) / (a_counts.sum() + buckets)
    return float(np.sum((a_frac - e_frac) * np.log(a_frac / e_frac)))


def ks_drift(expected: list[float], actual: list[float]) -> tuple[float, float]:
    """Return ``(statistic, p_value)`` from the two-sample KS test."""
    s = stats.ks_2samp(expected, actual)
    return float(s.statistic), float(s.pvalue)
