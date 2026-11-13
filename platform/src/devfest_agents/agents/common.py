"""Helpers shared by the agent builders."""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.base_toolset import BaseToolset
from google.genai import types

from ..config import REPO_ROOT

# The prompts participants edit live in my_agent/prompts; the rest live here.
PROMPT_DIRS = (REPO_ROOT / "my_agent" / "prompts", Path(__file__).parent / "prompts")

# role -> model; roles: "router" (main_agent, orchestrator) and "agent" (specialists)
ModelFactory = Callable[[str], Any]

GENERATION = types.GenerateContentConfig(temperature=0.2)


@lru_cache(maxsize=None)
def prompt_path(name: str) -> Path:
    for folder in PROMPT_DIRS:
        if (folder / f"{name}.md").exists():
            return folder / f"{name}.md"
    raise FileNotFoundError(f"No prompt {name}.md in {', '.join(str(d) for d in PROMPT_DIRS)}")


@lru_cache(maxsize=None)
def load_prompt(name: str) -> str:
    return prompt_path(name).read_text(encoding="utf-8")


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


def walk_agents(agent: LlmAgent):
    """The agent and every agent below it. AgentTool agents are not sub_agents, so follow the tools."""
    yield agent
    for tool in agent.tools:
        if isinstance(tool, AgentTool):
            yield from walk_agents(tool.agent)


async def list_tools(agent: LlmAgent) -> list[BaseTool]:
    """The agent's tools as the model sees them: toolsets expanded, plain functions wrapped."""
    tools: list[BaseTool] = []
    for item in agent.tools:
        if isinstance(item, BaseToolset):
            tools.extend(await item.get_tools())
        elif isinstance(item, BaseTool):
            tools.append(item)
        else:
            tools.append(FunctionTool(item))
    return tools


def tool_title(tool: BaseTool) -> str:
    """Registry tools have a title; Python tools use the first line of their docstring."""
    spec = getattr(tool, "spec", None)
    if spec is not None:
        return spec.title + (" (curated answer)" if spec.tool_type == "factual" else "")
    return (tool.description or "").strip().split("\n")[0]


CATALOGUE_LABEL_MAX = 120
_CONTROL = re.compile(r"[\x00-\x1f\x7f]+")
# Characters that could close our quoting, start markdown structure, or fake a [[MARKER]].
_MARKUP = re.compile(r"[`*_#>|<\[\]{}\\]")


def catalogue_label(text: str) -> str:
    """A tool title made safe to quote inside a system prompt.

    Titles come from the tools UI/API, i.e. from users. One line, no markdown, no quote
    characters, bounded length; the prompt then presents it as a quoted label, not as
    instructions. Defence in depth: write access to the registry is the primary control."""
    text = _CONTROL.sub(" ", text or "")
    text = _MARKUP.sub("", text).replace('"', "'")
    text = " ".join(text.split())
    if len(text) > CATALOGUE_LABEL_MAX:
        text = text[: CATALOGUE_LABEL_MAX - 1].rstrip() + "\u2026"
    return text
