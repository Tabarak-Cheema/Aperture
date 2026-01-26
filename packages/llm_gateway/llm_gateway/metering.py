"""Per-tenant token metering.

Every call through :class:`GatewayClient` writes a :class:`TokenUsage` row.
Admin dashboards aggregate these into TPAQ (tokens per answered question) and
cascade hit rates.

Budgets are enforced at two levels:

1. **Per-template** in CI: each prompt template is rendered against the largest
   fixture schema; the build fails if it exceeds its budget.
2. **Per-tenant** in production: monthly soft and hard caps. On the hard cap,
   the compile service falls back to T3 (local model) or offers the closest
   matching templates as clickable suggestions.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock


@dataclass(slots=True)
class TokenUsage:
    tenant_id: str
    tier: str
    input_tokens: int
    output_tokens: int
    at: datetime
    model: str
    ok: bool = True


@dataclass(slots=True)
class Meter:
    """In-process meter. The production meter persists to Postgres."""

    rows: list[TokenUsage] = field(default_factory=list)
    _lock: Lock = field(default_factory=Lock)

    def record(self, usage: TokenUsage) -> None:
        with self._lock:
            self.rows.append(usage)

    def total_for(self, tenant_id: str) -> tuple[int, int]:
        inp = out = 0
        for r in self.rows:
            if r.tenant_id == tenant_id:
                inp += r.input_tokens
                out += r.output_tokens
        return inp, out

    def by_tier(self, tenant_id: str) -> dict[str, int]:
        counts: dict[str, int] = defaultdict(int)
        for r in self.rows:
            if r.tenant_id == tenant_id:
                counts[r.tier] += 1
        return dict(counts)

    def tpaq(self, tenant_id: str, answered_questions: int) -> float:
        """Tokens per answered question."""
        if answered_questions <= 0:
            return 0.0
        inp, out = self.total_for(tenant_id)
        return (inp + out) / answered_questions
