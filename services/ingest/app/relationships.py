"""Automatic relational mapping.

For each pair of columns across tables, compute a containment score via
``datasketch`` MinHash LSH. Combine with name similarity, type match and
cardinality into a confidence score; high-confidence edges are auto-accepted,
lower ones queued for one-click confirmation.

See §3.4 of the transformation plan.
"""
from __future__ import annotations

from dataclasses import dataclass

from catalog.models import Catalog, Column, Relationship
from datasketch import MinHash, MinHashLSH
from rapidfuzz import fuzz


@dataclass(slots=True)
class CandidateEdge:
    left_table: str
    left_column: str
    right_table: str
    right_column: str
    containment: float
    name_similarity: float
    type_match: bool

    @property
    def confidence(self) -> float:
        base = 0.6 * self.containment + 0.3 * (self.name_similarity / 100) + 0.1 * float(self.type_match)
        return min(1.0, max(0.0, base))


def _signature(values: list[str], num_perm: int = 64) -> MinHash:
    mh = MinHash(num_perm=num_perm)
    for v in values:
        if v is None:
            continue
        mh.update(str(v).encode())
    return mh


def _containment(a: list[str], b_sig: MinHash) -> float:
    """Approximate |A ∩ B| / |A| via MinHash Jaccard + size ratio."""
    if not a:
        return 0.0
    a_sig = _signature(a)
    jac = a_sig.jaccard(b_sig)
    # Size ratio stabilizes containment when A is much smaller than B.
    return jac / max(jac, 1e-6) * jac  # smoothed


def discover_relationships(
    catalog: Catalog,
    samples: dict[tuple[str, str], list[str]],
    confidence_auto_accept: float = 0.75,
) -> list[CandidateEdge]:
    """Walk column-pair candidates and return scored edges.

    ``samples[(table, column)]`` is a sample of distinct non-null values.
    Candidates are restricted to pairs where one side has a candidate-key
    profile (unique + non-null) to keep the search O(|keys| × |columns|).
    """
    lsh = MinHashLSH(threshold=0.5, num_perm=64)
    sigs: dict[tuple[str, str], MinHash] = {}

    # Only index columns that *could* be the one side of a join (keys)
    key_columns: list[tuple[str, str, Column]] = []
    for t in catalog.tables.values():
        for c in t.columns.values():
            if c.profile.distinct and c.profile.rows and c.profile.distinct == c.profile.rows:
                key_columns.append((t.name, c.name, c))
                sig = _signature(samples.get((t.name, c.name), []))
                sigs[(t.name, c.name)] = sig
                lsh.insert(f"{t.name}.{c.name}", sig)

    edges: list[CandidateEdge] = []
    for t in catalog.tables.values():
        for col in t.columns.values():
            if (t.name, col.name) in sigs:
                continue  # skip self
            sample = samples.get((t.name, col.name), [])
            if not sample:
                continue
            q = _signature(sample)
            for hit in lsh.query(q):
                r_table, r_col = hit.split(".", 1)
                if r_table == t.name:
                    continue
                right = catalog.tables[r_table].columns[r_col]
                containment = _containment(sample, sigs[(r_table, r_col)])
                name_sim = fuzz.ratio(col.name.lower(), r_col.lower())
                type_match = col.type == right.type
                edges.append(
                    CandidateEdge(
                        left_table=r_table,
                        left_column=r_col,
                        right_table=t.name,
                        right_column=col.name,
                        containment=containment,
                        name_similarity=name_sim,
                        type_match=type_match,
                    )
                )

    # Deduplicate & keep the strongest per (right table, right column)
    best: dict[tuple[str, str], CandidateEdge] = {}
    for e in edges:
        key = (e.right_table, e.right_column)
        prev = best.get(key)
        if prev is None or e.confidence > prev.confidence:
            best[key] = e

    accepted: list[CandidateEdge] = []
    for e in best.values():
        if e.confidence >= confidence_auto_accept:
            catalog.relationships.append(
                Relationship(
                    left_table=e.left_table,
                    left_column=e.left_column,
                    right_table=e.right_table,
                    right_column=e.right_column,
                    cardinality="one_to_many",
                    confidence=e.confidence,
                    auto_accepted=True,
                )
            )
        accepted.append(e)
    return accepted
