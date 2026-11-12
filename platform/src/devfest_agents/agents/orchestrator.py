"""orchestrator: routes each question to the specialist agents.

Classification is just the LLM choosing function calls: every specialist is an
AgentTool, i.e. a function named after the agent whose description is the
agent's description. The instruction is a callable rebuilt every turn, so it
always carries today's date and a live catalogue of each specialist's tools -
registering a tool in the UI also improves routing.
"""

from __future__ import annotations

from typing import Any

from google.adk.agents import LlmAgent
from google.adk.tools.agent_tool import AgentTool

from .. import tracing
from .common import GENERATION, list_tools, render, tool_title

NAME = "orchestrator"
DESCRIPTION = (
    "Routes any Nimbus Markets data question to the specialist agents "
    "(in parallel when independent, sequentially when one answer depends on another) and returns a merged, "
    "attributed answer. Pass one self-contained question with explicit dates."
)


async def build_catalogue(specialists: list[LlmAgent]) -> str:
    lines: list[str] = []
    for agent in specialists:
        lines.append(f"- `{agent.name}`:")
        tools = await list_tools(agent)
        lines.extend(f"  - `{tool.name}`: {tool_title(tool)}" for tool in tools)
        if not tools:
            lines.append("  - (no tools yet)")
    return "\n".join(lines)


def make_instruction(specialists: list[LlmAgent]):
    async def orchestrator_instruction(ctx) -> str:  # ReadonlyContext
        return render(NAME, catalogue=await build_catalogue(specialists))

    return orchestrator_instruction


def build_orchestrator(model: Any, specialists: list[LlmAgent], guard: tracing.DelegationGuard) -> LlmAgent:
    agent = LlmAgent(
        name=NAME,
        model=model,
        description=DESCRIPTION,
        instruction=make_instruction(specialists),
        tools=[AgentTool(agent=a) for a in specialists],
        generate_content_config=GENERATION,
    )
    tracing.attach(agent, guard=guard)
    return agent
