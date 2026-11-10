"""main_agent: the root persona. Handles greetings/meta itself and sends every
data or news question to AgentTool(orchestrator), then writes the final answer."""

from __future__ import annotations

from typing import Any

from google.adk.agents import LlmAgent
from google.adk.tools.agent_tool import AgentTool

from .. import tracing
from .common import GENERATION, static_instruction

NAME = "main_agent"
DESCRIPTION = "Nimbus Markets analytics assistant (root agent): talks to the user and delegates to the orchestrator."


def build_main_agent(model: Any, orchestrator: LlmAgent, guard: tracing.DelegationGuard) -> LlmAgent:
    agent = LlmAgent(
        name=NAME,
        model=model,
        description=DESCRIPTION,
        instruction=static_instruction(NAME),
        tools=[AgentTool(agent=orchestrator)],
        generate_content_config=GENERATION,
    )
    tracing.attach(agent, guard=guard)
    return agent
