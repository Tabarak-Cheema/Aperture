"""LLM provider switchboard.

The user picks a provider in Settings and (for cloud providers) pastes an API
key. The key lives in ``~/.aperture/settings.json`` on their machine, never in
an env file, never committed.

Ollama is the recommended local-first option — no key needed, works offline.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import httpx
from llm_gateway import GatewayClient, Provider

PROVIDER_LABELS = {
    "ollama": "Ollama (local)",
    "groq": "Groq",
    "openai": "OpenAI",
    "together": "Together AI",
    "fireworks": "Fireworks AI",
    "mock": "Mock (offline tests)",
}

DEFAULT_MODELS = {
    "ollama": "llama3.2",
    "groq": "llama-3.3-70b-versatile",
    "openai": "gpt-4o-mini",
    "together": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
    "fireworks": "accounts/fireworks/models/llama-v3p3-70b-instruct",
    "mock": "mock",
}


@dataclass
class ProviderSpec:
    name: str
    label: str
    needs_key: bool
    default_model: str


def all_providers() -> list[ProviderSpec]:
    return [
        ProviderSpec("ollama", PROVIDER_LABELS["ollama"], False, DEFAULT_MODELS["ollama"]),
        ProviderSpec("groq", PROVIDER_LABELS["groq"], True, DEFAULT_MODELS["groq"]),
        ProviderSpec("openai", PROVIDER_LABELS["openai"], True, DEFAULT_MODELS["openai"]),
        ProviderSpec("together", PROVIDER_LABELS["together"], True, DEFAULT_MODELS["together"]),
        ProviderSpec("fireworks", PROVIDER_LABELS["fireworks"], True, DEFAULT_MODELS["fireworks"]),
        ProviderSpec("mock", PROVIDER_LABELS["mock"], False, DEFAULT_MODELS["mock"]),
    ]


def build_client(provider: str, api_key: str, model: str, ollama_base: str) -> GatewayClient:
    """Instantiate a GatewayClient for a user-selected provider.

    Falls back to mock when the user picks a cloud provider but hasn't entered
    a key — so the service keeps working for T0/T1/T2 while they set it up.
    """
    if provider == "ollama":
        # Ollama exposes an OpenAI-compatible endpoint at <base>/chat/completions.
        # We reuse the OpenAI client and swap the base URL via a subclass below.
        return OllamaClient(base_url=ollama_base, model=model or DEFAULT_MODELS["ollama"])
    if provider in ("groq", "openai", "together", "fireworks") and not api_key:
        return GatewayClient(provider=Provider.mock)
    try:
        p = Provider(provider)
    except ValueError:
        p = Provider.mock
    return GatewayClient(provider=p, api_key=api_key, model=model or None)


# -----------------------------------------------------------------------------
# Ollama: a thin subclass of GatewayClient with a custom base URL.
# -----------------------------------------------------------------------------
class OllamaClient(GatewayClient):
    def __init__(self, base_url: str, model: str):
        super().__init__(provider=Provider.openai, api_key="ollama", model=model)
        self._base = base_url.rstrip("/")

    async def complete_json(self, system, user, schema, tier="T4", max_output_tokens=120):
        """Override to hit the Ollama base URL directly.

        Ollama's /v1/chat/completions accepts the OpenAI format but ignores
        unknown fields like ``response_format=json_schema``; to still coerce
        JSON we fall back to ``format=json`` on the native /api/chat endpoint.
        """
        from llm_gateway.client import GatewayCall

        started = time.monotonic()
        http = await self._client()
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "format": "json",
            "options": {"temperature": 0, "num_predict": max_output_tokens},
        }
        try:
            # Prefer native /api/chat for JSON mode support.
            native = self._base.replace("/v1", "") + "/api/chat"
            r = await http.post(native, json=payload)
            r.raise_for_status()
            data = r.json()
            content = data.get("message", {}).get("content", "")
            prompt_eval = data.get("prompt_eval_count", 0)
            eval_count = data.get("eval_count", 0)
        except httpx.HTTPError as exc:
            return GatewayCall(
                tier=tier, provider=Provider.openai, model=self.model or "",
                input_tokens=0, output_tokens=0,
                latency_ms=int((time.monotonic() - started) * 1000),
                ok=False, error=f"ollama: {exc}",
            )

        return GatewayCall(
            tier=tier, provider=Provider.openai, model=self.model or "",
            input_tokens=prompt_eval, output_tokens=eval_count,
            latency_ms=int((time.monotonic() - started) * 1000),
            ok=True, content=content,
        )
