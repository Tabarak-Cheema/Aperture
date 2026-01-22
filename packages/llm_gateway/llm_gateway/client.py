"""Gateway client.

Thin OpenAI-compatible wrapper. Works with Groq, OpenAI, Together, Fireworks or
anything else that speaks /chat/completions. Switching provider is a config
change, never a code change.

Supports structured outputs (``response_format={"type":"json_schema",...}``) so
the model physically cannot return anything that isn't an AQIR plan.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import httpx


class Provider(StrEnum):
    groq = "groq"
    openai = "openai"
    together = "together"
    fireworks = "fireworks"
    mock = "mock"       # used by tests / CI


PROVIDER_BASE_URLS = {
    Provider.groq: "https://api.groq.com/openai/v1",
    Provider.openai: "https://api.openai.com/v1",
    Provider.together: "https://api.together.xyz/v1",
    Provider.fireworks: "https://api.fireworks.ai/inference/v1",
}

DEFAULT_MODELS = {
    Provider.groq: "llama-3.3-70b-versatile",
    Provider.openai: "gpt-4o-mini",
    Provider.together: "meta-llama/Llama-3.3-70B-Instruct-Turbo",
    Provider.fireworks: "accounts/fireworks/models/llama-v3p3-70b-instruct",
}


@dataclass(slots=True)
class GatewayCall:
    """One roundtrip through the gateway."""

    tier: str                           # T3 / T4 / T5
    provider: Provider
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    ok: bool
    content: str = ""
    error: str | None = None


@dataclass(slots=True)
class GatewayClient:
    provider: Provider = Provider.groq
    api_key: str | None = None
    model: str | None = None
    timeout_s: float = 20.0
    _http: httpx.AsyncClient | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.api_key is None:
            env_key = {
                Provider.groq: "GROQ_API_KEY",
                Provider.openai: "OPENAI_API_KEY",
                Provider.together: "TOGETHER_API_KEY",
                Provider.fireworks: "FIREWORKS_API_KEY",
                Provider.mock: "",
            }[self.provider]
            self.api_key = os.environ.get(env_key, "") if env_key else ""
        if self.model is None:
            self.model = DEFAULT_MODELS.get(self.provider, "")

    async def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=self.timeout_s)
        return self._http

    async def complete_json(
        self,
        system: str,
        user: str,
        schema: dict[str, Any],
        tier: str = "T4",
        max_output_tokens: int = 120,
    ) -> GatewayCall:
        """Return a structured JSON response that matches ``schema``.

        In ``Provider.mock`` mode this returns a canned success so CI doesn't
        need network. Real provider calls use ``response_format=json_schema``.
        """
        started = time.monotonic()

        if self.provider is Provider.mock:
            canned = '{"metrics":["revenue"],"dimensions":["region"]}'
            return GatewayCall(
                tier=tier,
                provider=self.provider,
                model="mock",
                input_tokens=len(system) // 4 + len(user) // 4,
                output_tokens=len(canned) // 4,
                latency_ms=1,
                ok=True,
                content=canned,
            )

        base = PROVIDER_BASE_URLS[self.provider]
        http = await self._client()
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.0,
            "max_tokens": max_output_tokens,
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "aqir_plan", "schema": schema, "strict": True},
            },
        }
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        try:
            r = await http.post(f"{base}/chat/completions", headers=headers, json=payload)
            r.raise_for_status()
        except httpx.HTTPError as exc:
            return GatewayCall(
                tier=tier,
                provider=self.provider,
                model=self.model or "",
                input_tokens=0,
                output_tokens=0,
                latency_ms=int((time.monotonic() - started) * 1000),
                ok=False,
                error=str(exc),
            )

        data = r.json()
        usage = data.get("usage", {})
        content = data["choices"][0]["message"]["content"]
        return GatewayCall(
            tier=tier,
            provider=self.provider,
            model=self.model or "",
            input_tokens=usage.get("prompt_tokens", 0),
            output_tokens=usage.get("completion_tokens", 0),
            latency_ms=int((time.monotonic() - started) * 1000),
            ok=True,
            content=content,
        )

    async def close(self) -> None:
        if self._http is not None:
            await self._http.aclose()
            self._http = None
