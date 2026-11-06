"""Helpers shared by the agent builders."""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Any

from google.genai import types

PROMPTS_DIR = Path(__file__).parent / "prompts"

# role -> model; roles: "router" (main_agent, orchestrator) and "agent" (specialists)
ModelFactory = Callable[[str], Any]

GENERATION = types.GenerateContentConfig(temperature=0.2)


@lru_cache(maxsize=None)
def load_prompt(name: str) -> str:
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")


def today() -> str:
    d = dt.date.today()
    return f"{d.isoformat()} ({d.strftime('%A')})"


def render(name: str, **values: str) -> str:
    """Fill [[KEY]] markers. Instructions are passed to ADK as callables, so ADK
    does not try to interpolate {state} placeholders in them."""
    text = load_prompt(name).replace("[[TODAY]]", today())
    for key, value in values.items():
        text = text.replace(f"[[{key.upper()}]]", value)
    return text


def static_instruction(name: str):
    def provider(ctx) -> str:  # ReadonlyContext
        return render(name)

    provider.__name__ = f"{name}_instruction"
    return provider
