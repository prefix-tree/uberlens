"""Models for the measurements, reached through OpenRouter."""

from __future__ import annotations

import os

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")
# The key is added to requests by the environment's network proxy; the client only needs a value to start.
os.environ.setdefault("OPENROUTER_API_KEY", "proxy-injected")

from pydantic_ai.models.openrouter import OpenRouterModel  # noqa: E402

_MAKERS = {"anthropic": "anthropic", "openai": "openai", "google": "google-ai-studio"}


def model(name: str) -> OpenRouterModel:
    return OpenRouterModel(name)


def settings(name: str, max_tokens: int, cache: bool = False) -> dict:
    """Keep every request of a run with the model's own maker.

    OpenRouter may send two requests of one conversation to different hosts of the same model. A reply
    that carries the model's signed reasoning is then refused by the second host.
    """
    out: dict = {"max_tokens": max_tokens}
    if cache:
        # The skill and the tool definitions are the same on every request, and the history only grows at its end.
        out |= {"openrouter_cache_instructions": True, "openrouter_cache_tool_definitions": True, "openrouter_cache_messages": True}
    if maker := _MAKERS.get(name.split("/")[0]):
        out["openrouter_provider"] = {"order": [maker], "allow_fallbacks": False}
    return out
