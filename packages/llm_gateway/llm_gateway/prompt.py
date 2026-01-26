"""Prompt builder.

A tiny static prefix that is byte-identical across calls, so providers that
discount cached input tokens charge less for most of each prompt. Only the
question, the schema slice, and a few retrieved examples vary.
"""
from __future__ import annotations

from dataclasses import dataclass

_SYSTEM = (
    "You are Aperture's query compiler. Produce an AQIR plan, not SQL. "
    "The JSON schema is attached via response_format; obey it exactly. "
    "Use only columns and tables present in the schema slice below. "
    "If the user asks for something you cannot express in the schema, return "
    '{"metrics":[],"_error":"<short reason>"}.'
)


@dataclass(slots=True)
class PromptBuilder:
    static_prefix: str = _SYSTEM

    def build(self, question: str, slice_text: str, examples: list[tuple[str, str]]) -> tuple[str, str]:
        """Return a ``(system, user)`` pair.

        The system message is byte-identical across tenants so provider-side
        prefix caching applies. The user message is short: slice + 3 examples +
        the question.
        """
        ex = "\n".join(f"Q: {q}\nA: {a}" for q, a in examples)
        user = (
            f"Schema slice:\n{slice_text}\n\n"
            f"Examples:\n{ex}\n\n"
            f"Question: {question}"
        )
        return self.static_prefix, user
