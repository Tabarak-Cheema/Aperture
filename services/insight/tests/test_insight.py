"""Insight service tests."""
from __future__ import annotations

import numpy as np

from services.insight.app.anomaly import detect_anomalies, psi
from services.insight.app.correlation import correlate_pairs
from services.insight.app.diffing import decompose_drivers, diff_metric


def test_diff_flags_significant_change():
    d = diff_metric(metric="revenue", history=[100.0] * 20, current=200.0)
    assert d is not None
    assert d.significant


def test_diff_no_flag_within_noise():
    rng = np.random.default_rng(1)
    hist = (100 + rng.normal(0, 5, size=30)).tolist()
    d = diff_metric(metric="revenue", history=hist, current=102.0)
    assert d is not None
    assert not d.significant


def test_driver_decomposition():
    drivers = decompose_drivers(
        previous_by_dim={"north": 50, "south": 50},
        current_by_dim={"north": 70, "south": 40},
    )
    # First driver explains the largest move
    assert drivers[0].dimension_value == "north"


def test_correlation_with_fdr():
    rng = np.random.default_rng(42)
    cols = {
        "a": rng.normal(0, 1, 300),
        "b": rng.normal(0, 1, 300),
        "c": rng.normal(0, 1, 300),  # irrelevant noise
    }
    # Make b perfectly correlated with a
    cols["b"] = cols["a"] * 2.0 + rng.normal(0, 0.1, 300)
    results = correlate_pairs(
        columns=cols,
        kinds={"a": "numeric", "b": "numeric", "c": "numeric"},
    )
    top = results[0]
    assert top.trust >= 50
    assert ({top.left, top.right}) == {"a", "b"}


def test_drift_detects_shift():
    rng = np.random.default_rng(0)
    expected = rng.normal(100, 5, 500).tolist()
    actual = (rng.normal(140, 5, 500)).tolist()  # mean shift
    p = psi(expected, actual)
    assert p > 0.2


def test_anomaly_detects_spike():
    series = [10.0] * 30
    series[15] = 90.0
    found = detect_anomalies(series, period=7, z_cutoff=3.0)
    assert any(a.index == 15 for a in found)
