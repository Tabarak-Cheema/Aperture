"""Entity linker: maps a user token to a column or value without the model.

Combines three signals:

* fuzzy string match (``rapidfuzz``) against column names and their synonyms,
* phonetic match (Soundex) for homophones,
* a distinct-value index per column, so "Karachi" can be resolved to
  ``customers.city``.

0 tokens. Deterministic. Hot path at T1 of the resolution cascade.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from rapidfuzz import fuzz, process


def _soundex(word: str) -> str:
    """Classic Soundex. Good enough for English BI terms."""
    if not word:
        return ""
    word = word.upper()
    codes = {c: d for d, letters in {
        "1": "BFPV", "2": "CGJKQSXZ", "3": "DT", "4": "L", "5": "MN", "6": "R",
    }.items() for c in letters}
    first = word[0]
    tail = []
    prev = codes.get(first, "")
    for ch in word[1:]:
        c = codes.get(ch, "")
        if c and c != prev:
            tail.append(c)
        prev = c
    out = (first + "".join(tail))[:4]
    return out + "0" * (4 - len(out))


@dataclass(slots=True)
class SynonymIndex:
    """Fuzzy + phonetic index over column names and learned synonyms.

    Populated once per catalog version; queried by the normalizer and the
    schema slicer.
    """

    canonical: dict[str, str] = field(default_factory=dict)     # synonym -> canonical
    by_phonetic: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    value_index: dict[str, set[str]] = field(default_factory=dict)  # column -> sampled values

    def add_name(self, canonical: str, synonyms: list[str]) -> None:
        self.canonical[canonical.lower()] = canonical
        for s in synonyms:
            self.canonical[s.lower()] = canonical
            self.by_phonetic[_soundex(s)].append(canonical)
        self.by_phonetic[_soundex(canonical)].append(canonical)

    def add_values(self, column: str, values: list[str]) -> None:
        bag = self.value_index.setdefault(column, set())
        for v in values:
            if v is None:
                continue
            bag.add(str(v))

    def resolve_token(self, token: str, min_score: int = 82) -> str | None:
        """Return the canonical name or value column for ``token``.

        Order: exact → fuzzy over names → phonetic → value index.
        """
        t = token.lower().strip()
        if not t:
            return None
        if t in self.canonical:
            return self.canonical[t]

        names = list(self.canonical.keys())
        match = process.extractOne(t, names, scorer=fuzz.WRatio, score_cutoff=min_score)
        if match is not None:
            return self.canonical[match[0]]

        phon = _soundex(token)
        if self.by_phonetic.get(phon):
            return self.by_phonetic[phon][0]

        for column, values in self.value_index.items():
            if token in values:
                return column

        return None

    def resolve_value(self, token: str) -> tuple[str, str] | None:
        """Given a token, find a column whose values contain it (case-insensitive)."""
        tl = token.lower()
        for column, values in self.value_index.items():
            for v in values:
                if v.lower() == tl:
                    return column, v
        return None
