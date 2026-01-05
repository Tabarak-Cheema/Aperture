"""AQIR schema (Pydantic v2).

The schema is deliberately small: the model's output is 60–120 tokens of JSON,
not 300+ of SQL. Constrained decoding against the JSON schema makes malformed
output impossible, and only SELECT-like semantics are expressible.
"""
from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Grain(StrEnum):
    """Time grain for the ``time`` clause."""

    day = "day"
    week = "week"
    month = "month"
    quarter = "quarter"
    year = "year"


class Op(StrEnum):
    """Allowed filter operators. Deliberately short."""

    eq = "="
    ne = "!="
    gt = ">"
    ge = ">="
    lt = "<"
    le = "<="
    in_ = "in"
    not_in = "not_in"
    like = "like"
    between = "between"
    is_null = "is_null"
    not_null = "not_null"


class SortDir(StrEnum):
    asc = "asc"
    desc = "desc"


class Filter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dim: str = Field(..., description="Column or dimension name (dotted path allowed).")
    op: Op
    value: str | int | float | bool | list[str | int | float] | None = None


class SortKey(BaseModel):
    model_config = ConfigDict(extra="forbid")

    by: str
    dir: SortDir = SortDir.desc


class TimeRange(BaseModel):
    """Relative or explicit time range.

    The normalizer resolves relative ranges to explicit [start, end] before the
    plan is hashed for the T0 cache, so a cache hit does not depend on *when* a
    question was asked.
    """

    model_config = ConfigDict(extra="forbid")

    dim: str = Field(..., description="Time column, e.g. 'order_date'.")
    range: str | None = Field(
        None,
        description="Relative keyword: today, yesterday, last_7d, last_30d, last_quarter, last_year, mtd, qtd, ytd.",
    )
    start: str | None = Field(None, description="ISO date YYYY-MM-DD, used when range is None.")
    end: str | None = Field(None, description="ISO date YYYY-MM-DD, inclusive.")
    grain: Grain | None = None


class Compare(BaseModel):
    """Ask for a comparison against a prior period on the same metric."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["yoy", "mom", "wow", "prev_period"] = "prev_period"


class JoinPath(BaseModel):
    """An optional explicit join hint (dotted path through the relationship graph)."""

    model_config = ConfigDict(extra="forbid")

    tables: list[str]


class AQIRPlan(BaseModel):
    """A typed query plan.

    Shape example::

        {
          "metrics": ["revenue"],
          "dimensions": ["region"],
          "filters": [{"dim": "country", "op": "=", "value": "PK"}],
          "time": {"dim": "order_date", "range": "last_quarter", "grain": "month"},
          "sort": [{"by": "revenue", "dir": "desc"}],
          "limit": 10
        }
    """

    model_config = ConfigDict(extra="forbid")

    metrics: list[str] = Field(..., min_length=1, max_length=8)
    dimensions: list[str] = Field(default_factory=list, max_length=6)
    filters: list[Filter] = Field(default_factory=list, max_length=20)
    time: TimeRange | None = None
    sort: list[SortKey] = Field(default_factory=list, max_length=4)
    limit: int | None = Field(None, ge=1, le=10_000)
    compare: Compare | None = None
    join_path: JoinPath | None = None

    @field_validator("metrics", "dimensions")
    @classmethod
    def _no_duplicates(cls, v: list[str]) -> list[str]:
        if len(v) != len(set(v)):
            raise ValueError("duplicate entries not allowed")
        return v

    def fingerprint(self) -> str:
        """Stable hash of the plan, used as the result-cache key.

        Independent of field insertion order and whitespace.
        """
        import hashlib

        data = self.model_dump_json(by_alias=False, exclude_none=True).encode()
        return hashlib.sha256(data).hexdigest()[:32]
