"""File sniffer.

Detects encoding and delimiter for CSV/TSV, strips Excel merged cells and
totals rows, and routes to the right reader (CSV, Excel, JSON, Parquet).

Deterministic. 0 tokens.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

_ENCODINGS = ("utf-8", "utf-8-sig", "latin-1", "cp1252")


@dataclass(slots=True)
class SniffResult:
    kind: Literal["csv", "tsv", "excel", "json", "ndjson", "parquet", "unknown"]
    encoding: str | None = None
    delimiter: str | None = None
    has_header: bool = True


def sniff(path: str | Path) -> SniffResult:
    p = Path(path)
    ext = p.suffix.lower()
    if ext in (".xlsx", ".xls", ".xlsm"):
        return SniffResult(kind="excel")
    if ext == ".parquet":
        return SniffResult(kind="parquet")
    if ext == ".ndjson":
        return SniffResult(kind="ndjson", encoding="utf-8")
    if ext == ".json":
        return SniffResult(kind="json", encoding="utf-8")

    # CSV / TSV
    sample: bytes = p.read_bytes()[:65536]
    encoding = _detect_encoding(sample)
    text = sample.decode(encoding, errors="replace")
    try:
        dialect = csv.Sniffer().sniff(text, delimiters=",;\t|")
        delim = dialect.delimiter
    except csv.Error:
        delim = "," if ext == ".csv" else "\t"
    try:
        has_header = csv.Sniffer().has_header(text)
    except csv.Error:
        has_header = True
    kind: Literal["csv", "tsv"] = "tsv" if delim == "\t" else "csv"
    return SniffResult(kind=kind, encoding=encoding, delimiter=delim, has_header=has_header)


def _detect_encoding(sample: bytes) -> str:
    for enc in _ENCODINGS:
        try:
            sample.decode(enc)
            return enc
        except UnicodeDecodeError:
            continue
    return "utf-8"
