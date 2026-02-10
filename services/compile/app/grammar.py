"""T2 — Analytic grammar.

A deterministic parser for the 40–60 phrasings that cover most BI questions:
``top N``, ``by``, ``per``, ``trend``, ``vs last month``, ``share of``,
``growth``, ``year over year``, etc. Zero tokens.

Unlike the template matcher (T1), this handles compositional phrasings; tokens
not spent as keywords are offered to the synonym index.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from aqir import AQIRPlan
from catalog import SynonymIndex

_STOPWORDS = {
    "the", "a", "an", "of", "for", "in", "on", "at", "to", "and", "please",
    "show", "me", "with",
}


@dataclass(slots=True)
class GrammarParser:
    """A tolerant parser that returns a plan or raises ValueError."""

    def parse(self, question: str, synonyms: SynonymIndex) -> AQIRPlan:
        q = question.lower().strip()

        # top N
        limit = None
        m = re.match(r"^top\s+(\d+)\s+(.*)$", q)
        if m:
            limit = int(m.group(1))
            q = m.group(2)

        # trend / over time -> grain
        grain: str | None = None
        m = re.search(r"\b(daily|weekly|monthly|quarterly|yearly)\b", q)
        if m:
            grain = {
                "daily": "day", "weekly": "week", "monthly": "month",
                "quarterly": "quarter", "yearly": "year",
            }[m.group(1)]
            q = q.replace(m.group(0), "")

        compare = None
        if re.search(r"\byear over year\b|\byoy\b", q):
            compare = {"kind": "yoy"}
        elif re.search(r"\bmonth over month\b|\bmom\b", q) or re.search(r"\bvs last month\b", q):
            compare = {"kind": "mom"}

        # Period keyword
        period = None
        for kw in ("today", "yesterday", "last 7 days", "last 30 days", "last quarter",
                   "last year", "ytd", "mtd", "qtd"):
            if kw in q:
                period = kw.replace(" ", "_").replace("7_days", "7d").replace("30_days", "30d")
                q = q.replace(kw, "")
                break

        # Split on "by"
        metrics: list[str] = []
        dims: list[str] = []
        if " by " in q:
            left, right = q.split(" by ", 1)
            metric_tok = self._first_token(left, synonyms)
            dim_tok = self._first_token(right, synonyms)
            if metric_tok:
                metrics.append(metric_tok)
            if dim_tok:
                dims.append(dim_tok)
        else:
            tok = self._first_token(q, synonyms)
            if tok:
                metrics.append(tok)

        if not metrics:
            raise ValueError("no metric found")

        body: dict = {"metrics": metrics}
        if dims:
            body["dimensions"] = dims
        if grain or period:
            body["time"] = {"dim": "order_date"}
            if grain:
                body["time"]["grain"] = grain
            if period:
                body["time"]["range"] = period
        if compare:
            body["compare"] = compare
        if limit:
            body["sort"] = [{"by": metrics[0], "dir": "desc"}]
            body["limit"] = limit
        return AQIRPlan.model_validate(body)

    @staticmethod
    def _first_token(phrase: str, synonyms: SynonymIndex) -> str | None:
        words = [w for w in re.findall(r"[a-z0-9_]+", phrase) if w not in _STOPWORDS]
        # Try longest prefix first
        for i in range(min(len(words), 4), 0, -1):
            tok = " ".join(words[:i])
            resolved = synonyms.resolve_token(tok)
            if resolved is not None:
                return resolved
        return None
