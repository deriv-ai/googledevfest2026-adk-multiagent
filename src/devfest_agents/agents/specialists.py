"""Shared builder for the two registry-backed specialists."""

from __future__ import annotations

from typing import Any

from google.adk.agents import LlmAgent

from ..tools.toolset import SqlRegistryToolset
from .common import GENERATION, static_instruction


def build_registry_specialist(*, name: str, schema: str, description: str, services: Any, model: Any) -> LlmAgent:
    toolset = SqlRegistryToolset(schema, services.cache(schema), services.run_tool)
    return LlmAgent(
        name=name,
        model=model,
        description=description,
        instruction=static_instruction(name),
        tools=[toolset],
        generate_content_config=GENERATION,
    )
