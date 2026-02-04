"""Question normalizer.

Lowercases, strips noise, expands common BI abbreviations, and resolves
relative time phrases to explicit ISO dates using the tenant's fiscal calendar.
The normalized question + catalog version is hashed for the T0 cache.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date, timedelta

_ABBREV = {
    "yoy": "year over year",
    "mom": "month over month",
    "wow": "week over week",
    "ytd": "year to date",
    "qtd": "quarter to date",
    "mtd": "month to date",
    "us": "united states",
    "uk": "united kingdom",
    "avg": "average",
    "q1": "first quarter",
    "q2": "second quarter",
    "q3": "third quarter",
    "q4": "fourth quarter",
}

_RELATIVE = re.compile(
    r"\b(today|yesterday|last\s+(?:7|30|90)\s*days?|last\s+week|last\s+month|"
    r"last\s+quarter|last\s+year|this\s+week|this\s+month|this\s+quarter|this\s+year)\b",
    re.IGNORECASE,
)


@dataclass(slots=True)
class Normalized:
    text: str
    relatives: dict[str, tuple[date, date]]
    fingerprint: str


def _expand_abbrev(text: str) -> str:
    def repl(m: re.Match) -> str:
        w = m.group(0).lower()
        return _ABBREV.get(w, w)

    return re.sub(r"\b\w+\b", repl, text.lower())


def _resolve_relative(phrase: str, today: date) -> tuple[date, date] | None:
    p = phrase.lower().replace("  ", " ").strip()
    if p == "today":
        return today, today
    if p == "yesterday":
        y = today - timedelta(days=1)
        return y, y
    if p == "last week":
        start = today - timedelta(days=today.weekday() + 7)
        return start, start + timedelta(days=6)
    if p in ("last month",):
        first_this = today.replace(day=1)
        last_prev = first_this - timedelta(days=1)
        first_prev = last_prev.replace(day=1)
        return first_prev, last_prev
    if p == "last quarter":
        q = (today.month - 1) // 3
        if q == 0:
            start = date(today.year - 1, 10, 1)
            end = date(today.year - 1, 12, 31)
        else:
            start = date(today.year, 3 * (q - 1) + 1, 1)
            end_month = 3 * q
            end = date(today.year, end_month, 30 if end_month != 2 else 28)
        return start, end
    if p == "last year":
        return date(today.year - 1, 1, 1), date(today.year - 1, 12, 31)
    m = re.match(r"last (\d+) days?", p)
    if m:
        n = int(m.group(1))
        return today - timedelta(days=n - 1), today
    return None


def normalize(
    question: str,
    catalog_version: int,
    tenant_id: str,
    today: date | None = None,
) -> Normalized:
    today = today or date.today()
    expanded = _expand_abbrev(question).strip()

    relatives: dict[str, tuple[date, date]] = {}
    for m in _RELATIVE.finditer(expanded):
        rng = _resolve_relative(m.group(0), today)
        if rng is not None:
            relatives[m.group(0).lower()] = rng

    # For the fingerprint, replace each relative phrase with its resolved dates.
    canon = expanded
    for phrase, (lo, hi) in relatives.items():
        canon = canon.replace(phrase, f"[{lo.isoformat()}..{hi.isoformat()}]")
    canon = re.sub(r"\s+", " ", canon).strip()

    h = hashlib.sha256(f"{tenant_id}|v{catalog_version}|{canon}".encode()).hexdigest()[:24]
    return Normalized(text=canon, relatives=relatives, fingerprint=h)
