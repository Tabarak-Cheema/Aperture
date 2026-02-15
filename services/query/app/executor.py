"""Query executor.

Takes compiled SQL + the plan hash + the data version and runs it against
DuckDB. A result cache (Redis in production; in-process dict in dev) keys on
``(plan_hash, data_version, rls_context)`` so repeated executions cost zero
database round-trips as well as zero model tokens.

Enforces:

* SELECT-only via sqlglot AST validation.
* EXPLAIN-based cost guard (reject plans exceeding ``MAX_SCANNED_ROWS``).
* Per-query time limit.
"""
from __future__ import annotations

import contextlib
import hashlib
import time
from dataclasses import dataclass, field
from typing import Any

import duckdb
import sqlglot
from sqlglot import exp

MAX_SCANNED_ROWS = 50_000_000
MAX_QUERY_SECONDS = 20.0


@dataclass(slots=True)
class ExecutionResult:
    rows: list[dict[str, Any]]
    columns: list[str]
    latency_ms: int
    row_count: int
    cached: bool = False
    data_version: int = 1


@dataclass
class ResultCache:
    _store: dict[str, ExecutionResult] = field(default_factory=dict)

    def key(self, plan_hash: str, data_version: int, rls: str = "") -> str:
        return hashlib.sha256(f"{plan_hash}|v{data_version}|{rls}".encode()).hexdigest()

    def get(self, key: str) -> ExecutionResult | None:
        hit = self._store.get(key)
        if hit is None:
            return None
        return ExecutionResult(
            rows=hit.rows, columns=hit.columns, latency_ms=hit.latency_ms,
            row_count=hit.row_count, cached=True, data_version=hit.data_version,
        )

    def put(self, key: str, result: ExecutionResult) -> None:
        self._store[key] = result


class CostGuardError(RuntimeError):
    pass


def _assert_select_only(sql: str) -> None:
    for stmt in sqlglot.parse(sql, dialect="duckdb"):
        if stmt is None:
            continue
        if not isinstance(stmt, (exp.Select, exp.With)):
            raise CostGuardError(f"non-SELECT statement rejected: {type(stmt).__name__}")


def _cost_estimate(con: duckdb.DuckDBPyConnection, sql: str) -> int:
    try:
        plan = con.execute(f"EXPLAIN {sql}").fetchall()
    except duckdb.Error:
        return 0
    # DuckDB's EXPLAIN is textual; look for ``EC=`` rows (estimated cardinality).
    total = 0
    for row in plan:
        text = " ".join(str(c) for c in row)
        for token in text.split():
            if token.startswith("EC="):
                with contextlib.suppress(ValueError):
                    total += int(token.split("=")[1])
    return total


class Executor:
    """A DuckDB executor with a result cache and a cost guard."""

    def __init__(self, database: str | None = None, cache: ResultCache | None = None):
        self._con = duckdb.connect(database or ":memory:")
        self._cache = cache or ResultCache()
        self._data_version = 1

    def bump_data_version(self) -> int:
        self._data_version += 1
        return self._data_version

    def register_table(self, name: str, path: str) -> None:
        """Register ``path`` as DuckDB view ``name``, format-sniffed by extension."""
        ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
        if ext == "parquet":
            reader = f"read_parquet('{path}')"
        elif ext in ("json", "ndjson"):
            reader = f"read_json_auto('{path}')"
        else:
            # Covers csv, tsv and unknown text formats; sample_size=-1 scans the
            # whole file for robust type inference on tiny fixtures.
            reader = f"read_csv_auto('{path}', sample_size=-1)"
        self._con.execute(f'CREATE OR REPLACE VIEW "{name}" AS SELECT * FROM {reader}')

    def execute(self, sql: str, plan_hash: str, rls: str = "") -> ExecutionResult:
        _assert_select_only(sql)
        key = self._cache.key(plan_hash, self._data_version, rls)
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        estimated = _cost_estimate(self._con, sql)
        if estimated > MAX_SCANNED_ROWS:
            raise CostGuardError(f"estimated {estimated:,} rows exceeds cap {MAX_SCANNED_ROWS:,}")

        started = time.monotonic()
        rel = self._con.execute(sql)
        columns = [d[0] for d in rel.description] if rel.description else []
        rows_tuple = rel.fetchall()
        elapsed = time.monotonic() - started
        if elapsed > MAX_QUERY_SECONDS:
            raise CostGuardError(f"query exceeded {MAX_QUERY_SECONDS}s")
        rows = [dict(zip(columns, r, strict=False)) for r in rows_tuple]
        result = ExecutionResult(
            rows=rows,
            columns=columns,
            latency_ms=int(elapsed * 1000),
            row_count=len(rows),
            cached=False,
            data_version=self._data_version,
        )
        self._cache.put(key, result)
        return result

    def close(self) -> None:
        self._con.close()
