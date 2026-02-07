"""Promoter — turns an accepted plan into a cache entry, a template and an example.

The learning flywheel. Every accept, edit or thumbs-down is a training signal
stored per tenant. TPAQ (tokens per answered question) should fall each week
for a given tenant; the admin console reads it from the meter.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from aqir import AQIRPlan


@dataclass(slots=True)
class PromotionRecord:
    tenant_id: str
    question: str
    plan_json: str
    source_tier: str
    accepted_by: str | None
    at: datetime


class Promoter:
    """In-memory promoter for the MVP; the production one writes to Postgres."""

    def __init__(self) -> None:
        self.records: list[PromotionRecord] = []

    def promote(
        self,
        *,
        tenant_id: str,
        question: str,
        plan: AQIRPlan,
        source_tier: str,
        accepted_by: str | None = None,
    ) -> PromotionRecord:
        r = PromotionRecord(
            tenant_id=tenant_id,
            question=question,
            plan_json=plan.model_dump_json(exclude_none=True),
            source_tier=source_tier,
            accepted_by=accepted_by,
            at=datetime.utcnow(),
        )
        self.records.append(r)
        return r
