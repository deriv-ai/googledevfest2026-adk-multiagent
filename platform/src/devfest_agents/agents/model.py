"""LiteLlm model factory.

Two modes (see docs/CONTRACT.md "LLM notes"):
* proxy  - OPENAI_BASE_URL is set: an OpenAI-compatible LiteLLM proxy; model
           strings use the ``openai/`` prefix and we pass api_base + api_key.
* direct - Gemini via LiteLLM's ``gemini/`` provider; api_key passed explicitly.

No max_tokens is set on purpose: Gemini 3.x spends reasoning tokens from the
completion budget, and a small cap returns empty answers.
"""

from __future__ import annotations

import os

from google.adk.models.lite_llm import LiteLlm

from ..config import Settings, get_settings

os.environ.setdefault("ADK_SUPPRESS_GEMINI_LITELLM_WARNINGS", "true")


def make_model(model: str, settings: Settings | None = None) -> LiteLlm:
    settings = settings or get_settings()
    kwargs: dict = {}
    key = settings.llm_api_key
    if key:
        kwargs["api_key"] = key
    if settings.llm_mode == "proxy":
        kwargs["api_base"] = settings.llm_api_base
    kwargs["timeout"] = settings.llm_timeout_seconds
    kwargs["num_retries"] = settings.llm_num_retries
    if settings.llm_reasoning_effort:
        kwargs["reasoning_effort"] = settings.llm_reasoning_effort
        kwargs["drop_params"] = True  # ignored by providers that don't support it
    return LiteLlm(model=model, **kwargs)


def agent_model(settings: Settings | None = None) -> LiteLlm:
    settings = settings or get_settings()
    return make_model(settings.effective_agent_model, settings)


def router_model(settings: Settings | None = None) -> LiteLlm:
    settings = settings or get_settings()
    return make_model(settings.effective_router_model, settings)
