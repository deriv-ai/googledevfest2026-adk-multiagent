"""orchestrator: routes each question to finance / trading / news specialists.

Classification is just the LLM choosing function calls: every specialist is an
AgentTool, i.e. a function named after the agent whose description is the
agent's description. The instruction is a callable rebuilt every turn, so it
always carries today's date and a live catalogue of each specialist's enabled
tools - registering a tool in the UI also improves routing.
"""

from __future__ import annotations

from typing import Any

from google.adk.agents import LlmAgent
from google.adk.tools.agent_tool import AgentTool

from .. import tracing
from ..tools.news_toolset import NEWS_TOOLS
from .common import GENERATION, render

NAME = "orchestrator"
DESCRIPTION = (
    "Routes any Nimbus Markets data or market-news question to the finance, trading and news specialists "
    "(in parallel when independent, sequentially when one answer depends on another) and returns a merged, "
    "attributed answer. Pass one self-contained question with explicit dates."
)


async def build_catalogue(services: Any) -> str:
    lines: list[str] = []
    for agent_name, schema in (("finance_agent", "finance"), ("trading_agent", "trading")):
        specs, _ = await services.cache(schema).refresh()
        lines.append(f"- `{agent_name}`:")
        if specs:
            for spec in specs:
                kind = "" if spec.tool_type == "sql" else " (curated answer)"
                lines.append(f"  - `{spec.name}`: {spec.title}{kind}")
        else:
            lines.append("  - (no tools registered yet)")
    news = services.news()
    names = getattr(news, "last_tool_names", None) or list(NEWS_TOOLS)
    status = "" if getattr(news, "available", True) else " (news server currently unreachable)"
    lines.append(f"- `news_agent`{status}:")
    for name in names:
        lines.append(f"  - `{name}`: {NEWS_TOOLS.get(name, 'news tool')}")
    return "\n".join(lines)


def make_instruction(services: Any):
    async def orchestrator_instruction(ctx) -> str:  # ReadonlyContext
        return render(NAME, catalogue=await build_catalogue(services))

    return orchestrator_instruction


def build_orchestrator(services: Any, model: Any, specialists: list[LlmAgent],
                       guard: tracing.DelegationGuard) -> LlmAgent:
    agent = LlmAgent(
        name=NAME,
        model=model,
        description=DESCRIPTION,
        instruction=make_instruction(services),
        tools=[AgentTool(agent=a) for a in specialists],
        generate_content_config=GENERATION,
    )
    tracing.attach(agent, guard=guard)
    return agent
