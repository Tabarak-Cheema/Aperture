"""Catalog data models.

The catalog is the single source of truth about a tenant's data: which tables
exist, which columns they have, their profiles (type, cardinality, null share,
sample values) and the relationships between them.

Every change to the catalog bumps a monotonic ``version`` integer. The plan
cache and result cache key on ``(plan_hash, catalog_version)`` so stale plans
are never reused after a schema change.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Literal


class ColumnType(StrEnum):
    string = "string"
    number = "number"
    integer = "integer"
    boolean = "boolean"
    date = "date"
    datetime = "datetime"
    percent = "percent"
    currency = "currency"
    id = "id"
    pii = "pii"
    unknown = "unknown"


@dataclass(slots=True)
class ColumnProfile:
    rows: int = 0
    distinct: int = 0
    null_share: float = 0.0
    min_value: str | None = None
    max_value: str | None = None
    sample_values: list[str] = field(default_factory=list)
    is_pii: bool = False
    pii_kind: str | None = None


@dataclass(slots=True)
class Column:
    name: str
    type: ColumnType
    description: str = ""
    profile: ColumnProfile = field(default_factory=ColumnProfile)


@dataclass(slots=True)
class TableProfile:
    rows: int = 0
    last_loaded_at: datetime | None = None
    source_path: str | None = None


@dataclass(slots=True)
class Table:
    name: str
    columns: dict[str, Column] = field(default_factory=dict)
    primary_key: list[str] = field(default_factory=list)
    profile: TableProfile = field(default_factory=TableProfile)

    def add_column(self, column: Column) -> None:
        self.columns[column.name] = column


@dataclass(slots=True)
class Relationship:
    left_table: str
    left_column: str
    right_table: str
    right_column: str
    cardinality: Literal["one_to_one", "one_to_many", "many_to_many"] = "one_to_many"
    confidence: float = 1.0
    auto_accepted: bool = False


@dataclass(slots=True)
class Catalog:
    tenant_id: str
    version: int = 1
    tables: dict[str, Table] = field(default_factory=dict)
    relationships: list[Relationship] = field(default_factory=list)

    def add_table(self, table: Table) -> None:
        self.tables[table.name] = table
        self.version += 1

    def many_sides(self) -> set[str]:
        """Return tables that are on the ``many`` side of at least one relationship."""
        out: set[str] = set()
        for r in self.relationships:
            if r.cardinality == "one_to_many":
                # convention: left is ``one`` side, right is ``many``
                out.add(r.right_table)
            elif r.cardinality == "many_to_many":
                out.add(r.left_table)
                out.add(r.right_table)
        return out

    def join_edges(self) -> dict[tuple[str, str], str]:
        edges: dict[tuple[str, str], str] = {}
        for r in self.relationships:
            key = (r.left_table, r.right_table)
            edges[key] = f"ON {r.left_table}.{r.left_column} = {r.right_table}.{r.right_column}"
        return edges
