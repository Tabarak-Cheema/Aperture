"""Tests for the catalog, semantic layer, and synonym index."""
from __future__ import annotations

from pathlib import Path

from catalog import (
    Catalog,
    Relationship,
    SynonymIndex,
    Table,
    load_semantic_yaml,
)
from catalog.semantic import DimensionYAML, MetricYAML, SemanticLayer, dump_semantic_yaml


def test_catalog_version_bumps():
    cat = Catalog(tenant_id="t")
    v0 = cat.version
    cat.add_table(Table(name="orders"))
    assert cat.version == v0 + 1


def test_many_sides_discovered():
    cat = Catalog(tenant_id="t")
    cat.tables = {
        "customers": Table(name="customers"),
        "orders": Table(name="orders"),
    }
    cat.relationships.append(
        Relationship("customers", "id", "orders", "customer_id", cardinality="one_to_many")
    )
    assert "orders" in cat.many_sides()
    assert "customers" not in cat.many_sides()


def test_synonym_exact_and_fuzzy():
    idx = SynonymIndex()
    idx.add_name("revenue", ["sales", "gmv", "turnover"])
    idx.add_name("region", ["area", "zone"])
    assert idx.resolve_token("sales") == "revenue"
    assert idx.resolve_token("Revenue") == "revenue"
    # Fuzzy
    assert idx.resolve_token("revnue") == "revenue"


def test_synonym_value_index():
    idx = SynonymIndex()
    idx.add_name("city", ["town"])
    idx.add_values("customers.city", ["Karachi", "Lahore", "Islamabad"])
    assert idx.resolve_value("Karachi") == ("customers.city", "Karachi")


def test_yaml_roundtrip(tmp_path: Path):
    layer = SemanticLayer()
    layer.metrics["revenue"] = MetricYAML(
        name="revenue", expr="SUM(orders.total_amount)", base_table="orders"
    )
    layer.dimensions["region"] = DimensionYAML(
        name="region", expr="customers.region", base_table="customers"
    )
    p = tmp_path / "sem.yaml"
    dump_semantic_yaml(layer, p)
    loaded = load_semantic_yaml(p)
    assert "revenue" in loaded.metrics
    assert loaded.dimensions["region"].expr == "customers.region"
