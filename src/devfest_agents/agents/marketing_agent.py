"""marketing_agent: answers campaign questions with hand-written Python tools over the marketing schema.

Workshop: GUIDE.md walks you through this file. Each TODO is one step.
"""

from __future__ import annotations

from typing import Any

from google.adk.agents import LlmAgent

from ..tools.sql_query import run_sql  # noqa: F401 - your tools use it (steps 1 and 2)
from .common import GENERATION, static_instruction  # noqa: F401 - build() uses them (step 3)

NAME = "marketing_agent"
LABEL = "Marketing agent"
DATASOURCE = "marketing"

# TODO step 3: tell the orchestrator what this agent is good at.
DESCRIPTION = ""


# TODO step 1: CAMPAIGN_PERFORMANCE_SQL and campaign_performance()


# TODO step 2: CHANNEL_SUMMARY_SQL and channel_summary()


def build(services: Any, model: Any) -> LlmAgent:
    # TODO step 3: return an LlmAgent that uses your tools.
    raise NotImplementedError("Follow GUIDE.md step 3")
