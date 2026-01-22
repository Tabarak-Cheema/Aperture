"""LLM gateway — the ONLY path in the codebase that can reach a cloud model.

Enforced by the CI test in ``.github/workflows/`` that fails the build when any
render-path module imports this package.
"""
from llm_gateway.client import GatewayCall, GatewayClient, Provider
from llm_gateway.metering import Meter, TokenUsage
from llm_gateway.prompt import PromptBuilder

__all__ = [
    "GatewayCall",
    "GatewayClient",
    "Meter",
    "PromptBuilder",
    "Provider",
    "TokenUsage",
]
