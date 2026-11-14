"""LiteLlm model factory.

Two modes:
* proxy  - OPENAI_BASE_URL is set: an OpenAI-compatible LiteLLM proxy; model
           strings use the ``openai/`` prefix and we pass api_base + api_key.
* direct - Gemini via LiteLLM's ``gemini/`` provider; api_key passed explicitly.

No max_tokens is set on purpose: Gemini 3.x spends reasoning tokens from the
completion budget, and a small cap returns empty answers.
"""

from __future__ import annotations

import asyncio
import collections
import os
import time
from typing import Any

from google.adk.models.lite_llm import LiteLlm, LiteLLMClient

from ..config import Settings, get_settings

os.environ.setdefault("ADK_SUPPRESS_GEMINI_LITELLM_WARNINGS", "true")


class RateLimiter:
    """At most `per_minute` calls in any 60 seconds; later callers wait their turn."""

    def __init__(self, per_minute: int) -> None:
        self.per_minute = per_minute
        self.calls: collections.deque[float] = collections.deque()
        self.lock = asyncio.Lock()

    async def wait(self) -> None:
        async with self.lock:
            while True:
                now = time.monotonic()
                while self.calls and now - self.calls[0] >= 60:
                    self.calls.popleft()
                if len(self.calls) < self.per_minute:
                    self.calls.append(now)
                    return
                await asyncio.sleep(60 - (now - self.calls[0]) + 0.1)


_limiters: dict[tuple[int, int], RateLimiter] = {}


def shared_limiter(per_minute: int) -> RateLimiter:
    """One limiter per event loop, shared by every agent, so the whole app stays under the quota."""
    key = (id(asyncio.get_running_loop()), per_minute)
    if key not in _limiters:
        _limiters[key] = RateLimiter(per_minute)
    return _limiters[key]


class RateLimitedClient(LiteLLMClient):
    """ADK's LiteLLM client, paced for a free Google AI Studio key (15 requests a minute per model)."""

    def __init__(self, per_minute: int) -> None:
        super().__init__()
        self.per_minute = per_minute

    async def acompletion(self, model: Any, messages: Any, tools: Any, **kwargs: Any):
        await shared_limiter(self.per_minute).wait()
        return await super().acompletion(model=model, messages=messages, tools=tools, **kwargs)


def make_model(model: str, settings: Settings | None = None) -> LiteLlm:
    settings = settings or get_settings()
    kwargs: dict = {}
    if settings.effective_requests_per_minute:
        kwargs["llm_client"] = RateLimitedClient(settings.effective_requests_per_minute)
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
