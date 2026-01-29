"""Profiler.

Reads a dataset with DuckDB (which handles CSV, Parquet and most Excel out of
the box) and produces a :class:`TableProfile` with:

* probabilistic type inference (date, datetime, currency, percent, PII patterns)
* cardinality and null share
* sampled values
* candidate keys (columns unique and non-null)

Schema generation is produced from the profile, never by an LLM. 0 tokens per
upload.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import duckdb
from catalog.models import Column, ColumnProfile, ColumnType, Table, TableProfile

_DATE_PATTERNS = [
    re.compile(r"^\d{4}-\d{2}-\d{2}$"),
    re.compile(r"^\d{2}/\d{2}/\d{4}$"),
    re.compile(r"^\d{1,2}-[A-Za-z]{3}-\d{4}$"),
]
_DATETIME = re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}")
_PERCENT = re.compile(r"^-?\d+(\.\d+)?%$")
_CURRENCY = re.compile(r"^[-$£€₹]?\d{1,3}(,\d{3})*(\.\d+)?$")
_EMAIL = re.compile(r"^[\w.+-]+@[\w-]+\.[\w.-]+$")
_PHONE = re.compile(r"^\+?\d[\d \-]{7,}\d$")
_CNIC = re.compile(r"^\d{5}-\d{7}-\d$")
_SSN = re.compile(r"^\d{3}-\d{2}-\d{4}$")


@dataclass(slots=True)
class ProfileConfig:
    sample_rows: int = 2000
    max_sample_values: int = 12


def _classify(values: list[str]) -> tuple[ColumnType, bool, str | None]:
    """Best-effort type classification from a list of non-null string values."""
    if not values:
        return ColumnType.unknown, False, None

    v_head = values[: min(len(values), 200)]

    def frac(pattern: re.Pattern) -> float:
        return sum(1 for v in v_head if pattern.match(v)) / len(v_head)

    # Check structured temporal patterns first; date formats can collide with
    # the loose phone regex (e.g. YYYY-MM-DD looks like a long dashed number).
    if frac(_DATETIME) > 0.8:
        return ColumnType.datetime, False, None
    if any(frac(p) > 0.8 for p in _DATE_PATTERNS):
        return ColumnType.date, False, None
    if frac(_EMAIL) > 0.8:
        return ColumnType.pii, True, "email"
    if frac(_CNIC) > 0.8:
        return ColumnType.pii, True, "cnic"
    if frac(_SSN) > 0.8:
        return ColumnType.pii, True, "ssn"
    if frac(_PHONE) > 0.8:
        return ColumnType.pii, True, "phone"
    if frac(_PERCENT) > 0.8:
        return ColumnType.percent, False, None
    if frac(_CURRENCY) > 0.8:
        return ColumnType.currency, False, None

    def is_int(s: str) -> bool:
        return bool(re.match(r"^-?\d+$", s))

    def is_float(s: str) -> bool:
        return bool(re.match(r"^-?\d+(\.\d+)?$", s))

    if sum(1 for v in v_head if is_int(v)) / len(v_head) > 0.9:
        return ColumnType.integer, False, None
    if sum(1 for v in v_head if is_float(v)) / len(v_head) > 0.9:
        return ColumnType.number, False, None
    if all(v.lower() in ("true", "false", "yes", "no", "0", "1") for v in v_head):
        return ColumnType.boolean, False, None
    return ColumnType.string, False, None


def profile_file(path: str | Path, table_name: str, cfg: ProfileConfig | None = None) -> Table:
    """Return a :class:`Table` populated with profiles and candidate keys."""
    cfg = cfg or ProfileConfig()
    p = Path(path)
    con = duckdb.connect(":memory:")
    # DuckDB's auto_detect read handles CSV, Parquet, Excel (with the spatial
    # extension) and JSON. For the MVP we use read_csv_auto / read_parquet.
    if p.suffix.lower() in (".parquet",):
        con.execute(f"CREATE VIEW t AS SELECT * FROM read_parquet('{p}')")
    elif p.suffix.lower() in (".xlsx", ".xls"):
        con.execute("INSTALL spatial; LOAD spatial;")
        con.execute(f"CREATE VIEW t AS SELECT * FROM st_read('{p}')")
    else:
        con.execute(f"CREATE VIEW t AS SELECT * FROM read_csv_auto('{p}', sample_size=-1)")

    schema = con.execute("DESCRIBE t").fetchall()  # (col_name, col_type, ...)
    (rows,) = con.execute("SELECT COUNT(*) FROM t").fetchone()
    table = Table(name=table_name, profile=TableProfile(rows=rows, source_path=str(p)))

    for col_name, _duck_type, *_ in schema:
        sample = con.execute(
            f'SELECT CAST("{col_name}" AS VARCHAR) AS v FROM t WHERE "{col_name}" IS NOT NULL LIMIT ?',
            (cfg.sample_rows,),
        ).fetchall()
        values = [r[0] for r in sample if r[0] is not None]
        kind, is_pii, pii_kind = _classify(values)
        (nulls,) = con.execute(
            f'SELECT COUNT(*) FROM t WHERE "{col_name}" IS NULL'
        ).fetchone()
        (distinct,) = con.execute(
            f'SELECT COUNT(DISTINCT "{col_name}") FROM t'
        ).fetchone()

        prof = ColumnProfile(
            rows=rows,
            distinct=distinct,
            null_share=(nulls / rows) if rows else 0.0,
            sample_values=values[: cfg.max_sample_values],
            is_pii=is_pii,
            pii_kind=pii_kind,
        )
        table.add_column(
            Column(
                name=col_name,
                type=kind,
                description=_describe(col_name, kind, prof),
                profile=prof,
            )
        )

    # Candidate keys: columns with distinct == rows and 0 nulls
    for c in table.columns.values():
        if c.profile.distinct == rows and c.profile.null_share == 0.0:
            table.primary_key.append(c.name)
            break  # first candidate wins for the MVP
    con.close()
    return table


def _describe(col_name: str, kind: ColumnType, prof: ColumnProfile) -> str:
    """Short, template-generated description. 0 tokens."""
    bits = [f"{kind.value} column"]
    if prof.distinct and prof.rows:
        bits.append(f"{prof.distinct} distinct")
    if prof.null_share > 0.01:
        bits.append(f"{prof.null_share:.0%} null")
    if prof.sample_values:
        preview = ", ".join(repr(v) for v in prof.sample_values[:3])
        bits.append(f"e.g. {preview}")
    return f"{col_name}: " + "; ".join(bits)
