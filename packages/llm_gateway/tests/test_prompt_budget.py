"""CI budget tests.

Each prompt template is rendered against the largest fixture schema. The build
fails if any rendered prompt exceeds its tier's token budget. See §6 of the
transformation plan.

We approximate token count as ``ceil(len(text) / 4)`` which overestimates
slightly for English + JSON, so this is a safe upper bound.
"""
from __future__ import annotations

from datetime import datetime

import pytest
from llm_gateway import Meter, PromptBuilder, TokenUsage


def _approx_tokens(s: str) -> int:
    return -(-len(s) // 4)


LARGE_SLICE = (
    "orders(id PK, cust_id -> customers.id, total_amount money, order_date date, status string)\n"
    "customers(id PK, name string, country string, region string, signup_date date)\n"
    "products(id PK, name string, category string, cost money, price money)\n"
    "order_items(id PK, order_id -> orders.id, product_id -> products.id, qty int, line_total money)\n"
    "suppliers(id PK, name string, country string)\n"
    "shipments(id PK, order_id -> orders.id, carrier string, shipped_at datetime, delivered_at datetime)\n"
)


T4_INPUT_BUDGET = 800
T4_OUTPUT_BUDGET = 120


@pytest.mark.parametrize(
    "question",
    [
        "revenue by region last quarter",
        "top 10 products by gross margin in 2026",
        "weekly active customers trend for the US over the last 12 months",
    ],
)
def test_t4_prompt_under_budget(question: str) -> None:
    pb = PromptBuilder()
    system, user = pb.build(
        question=question,
        slice_text=LARGE_SLICE,
        examples=[
            ("revenue by region", '{"metrics":["revenue"],"dimensions":["region"]}'),
            ("top 10 products by cost", '{"metrics":["cost"],"dimensions":["product"],"limit":10}'),
            ("orders by country last month", '{"metrics":["order_count"],"dimensions":["country"]}'),
        ],
    )
    total_in = _approx_tokens(system) + _approx_tokens(user)
    assert total_in <= T4_INPUT_BUDGET, f"T4 prompt exceeds budget: {total_in} > {T4_INPUT_BUDGET}"


def test_meter_tpaq():
    m = Meter()
    m.record(TokenUsage("t", "T4", 500, 90, datetime.utcnow(), "llama"))
    m.record(TokenUsage("t", "T0", 0, 0, datetime.utcnow(), ""))
    m.record(TokenUsage("t", "T0", 0, 0, datetime.utcnow(), ""))
    assert m.tpaq("t", answered_questions=3) == pytest.approx((500 + 90) / 3)
    assert m.by_tier("t") == {"T4": 1, "T0": 2}
