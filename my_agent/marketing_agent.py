"""marketing_agent: answers Vernon's campaign questions.

The data team's queries are in marketing_queries.py. You turn them into tools,
give the tools to an agent, and plug the agent into the orchestrator.
The exercises in exercises/ walk you through it.
"""

from __future__ import annotations

from typing import Any

from google.adk.agents import LlmAgent

from . import marketing_queries as queries  # noqa: F401 - your tools call these (exercise 1)
from devfest_agents.agents.common import GENERATION, static_instruction  # noqa: F401 - build() uses them (exercise 2)

NAME = "marketing_agent"
LABEL = "Marketing agent"
DATASOURCE = "marketing"

# Exercise 2: what is this agent good at? The orchestrator reads only this.
DESCRIPTION = ""


# Exercise 1: your tools go here.


def build(services: Any, model: Any) -> LlmAgent:
    # Exercise 2: return an LlmAgent that uses your tools.
    raise NotImplementedError("marketing_agent.build() is exercise 2")
