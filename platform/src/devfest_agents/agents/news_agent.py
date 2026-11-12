"""news_agent: live market news through the news-mcp server (fail-soft McpToolset)."""

from __future__ import annotations

from typing import Any

from google.adk.agents import LlmAgent

from .common import GENERATION, static_instruction

NAME = "news_agent"
LABEL = "News agent"
DATASOURCE = "internet"
DESCRIPTION = (
    "News specialist. Finds recent real-world market headlines and searches news about an instrument, "
    "asset class or economic event (live RSS feeds). Has no Nimbus company data. "
    "Pass one self-contained request, e.g. 'Latest news about Bitcoin'."
)


def build(services: Any, model: Any) -> LlmAgent:
    return LlmAgent(
        name=NAME,
        model=model,
        description=DESCRIPTION,
        instruction=static_instruction(NAME),
        tools=[services.news()],
        generate_content_config=GENERATION,
    )
