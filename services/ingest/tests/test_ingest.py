"""Tests for the ingest service: sniffer, profiler, relationship discovery."""
from __future__ import annotations

import csv
from pathlib import Path

import pytest

from services.ingest.app.profiler import profile_file
from services.ingest.app.sniffer import sniff


@pytest.fixture
def orders_csv(tmp_path: Path) -> Path:
    p = tmp_path / "orders.csv"
    with p.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["id", "customer_id", "total_amount", "order_date", "email"])
        for i in range(1, 51):
            w.writerow([i, (i % 7) + 1, f"{i * 12.5:.2f}", f"2026-02-{(i % 28) + 1:02}",
                        f"user{i}@example.com"])
    return p


def test_sniff_csv(orders_csv):
    r = sniff(orders_csv)
    assert r.kind == "csv"
    assert r.delimiter == ","
    assert r.has_header is True


def test_profile_detects_types(orders_csv):
    table = profile_file(orders_csv, table_name="orders")
    assert table.profile.rows == 50
    assert set(table.columns) == {"id", "customer_id", "total_amount", "order_date", "email"}
    assert table.columns["email"].profile.is_pii
    assert table.columns["order_date"].type.value in ("date", "datetime")
    # id is unique -> becomes a candidate primary key
    assert "id" in table.primary_key
