"""Check one workshop exercise: python -m devfest_agents.check <0-3>

Prints a checklist with a tick or a cross per item, and a hint for every cross.
None of the checks calls the LLM, so they cost nothing on your key.
"""

from __future__ import annotations

import asyncio
import inspect
import sys
from typing import Any

from .evals import NO, OK
from .services import get_services
from .tools.sql_query import run_sql

SAMPLE_ARGS = {"start_date": "2026-07-01", "end_date": "2026-09-30"}
GAP_HEADING = "## Not covered yet"  # in my_agent/prompts/orchestrator.md until exercise 3

# Exercise 1: the two data-team queries participants wrap themselves.
YOUR_QUERIES = {"fetch_campaign_performance": "one row per campaign",
                "fetch_channel_summary": "one row per ad channel"}


class Checklist:
    def __init__(self) -> None:
        self.failed = 0

    def ok(self, text: str) -> None:
        print(f"  {OK} {text}")

    def fail(self, text: str, hint: str = "") -> None:
        self.failed += 1
        print(f"  {NO} {text}" + (f"\n      {hint}" if hint else ""))

    def check(self, passed: bool, text: str, hint: str = "") -> bool:
        self.ok(text) if passed else self.fail(text, hint)
        return passed


def marketing_module():
    from my_agent import marketing_agent

    return marketing_agent


def tool_functions(module) -> list[Any]:
    """The async functions written in marketing_agent.py: the tools."""
    return [f for name, f in vars(module).items()
            if inspect.iscoroutinefunction(f) and f.__module__ == module.__name__ and not name.startswith("_")]


def your_tools(module) -> list[Any]:
    """The tools the participant wrote: every tool except the ready-made ones."""
    ready = getattr(module, "READY_MADE_TOOLS", [])
    return [f for f in tool_functions(module) if f not in ready]


# ---------------------------------------------------------------------------
async def exercise_0(c: Checklist) -> None:
    c.check(get_services().settings.llm_key_configured, "An LLM key is set",
            "Add LLM_API_KEY (and AGENT_MODEL) to .env, then run `make up` again. See step 2 of Set up in README.md.")
    result = await run_sql("marketing", "SELECT COUNT(*) AS n FROM marketing.campaigns")
    c.check("rows" in result and result["rows"][0]["n"] > 0, "The database has the marketing data",
            result.get("error", "Run `make reset` to reload the data."))


async def exercise_1(c: Checklist) -> None:
    from google.adk.tools import FunctionTool

    tools = your_tools(marketing_module())
    for query, shape in YOUR_QUERIES.items():
        c.check(any(f"queries.{query}(" in inspect.getsource(t) for t in tools),
                f"A tool of yours calls queries.{query} ({shape})",
                f"Write an `async def` tool in my_agent/marketing_agent.py that returns `await queries.{query}(...)`.")
    for tool in tools:
        name, doc = tool.__name__, inspect.getdoc(tool) or ""
        c.check(len(doc) >= 40, f"{name} has a docstring",
                "Gemini only sees the name, the parameters and the docstring. Say what it returns and when to use it.")
        untyped = [p.name for p in inspect.signature(tool).parameters.values() if p.annotation is p.empty]
        c.check(not untyped, f"{name} has type hints on every parameter",
                f"Add a type to: {', '.join(untyped)}. ADK turns the hints into the tool's schema.")
        try:
            FunctionTool(tool)._get_declaration()
            c.ok(f"ADK can turn {name} into a tool")
        except Exception as exc:  # noqa: BLE001
            c.fail(f"ADK can turn {name} into a tool", f"{type(exc).__name__}: {exc}")
        await check_tool_runs(c, tool)


async def check_tool_runs(c: Checklist, tool) -> None:
    params = inspect.signature(tool).parameters.values()
    unknown = [p.name for p in params if p.default is p.empty and p.name not in SAMPLE_ARGS]
    if unknown:
        c.ok(f"{tool.__name__}: not run, it needs {', '.join(unknown)} (that's fine)")
        return
    result = await tool(**{p.name: SAMPLE_ARGS[p.name] for p in params if p.name in SAMPLE_ARGS})
    if isinstance(result, dict) and "rows" in result:
        c.ok(f"{tool.__name__} returns data ({result['row_count']} rows for Q3 2026)")
    else:
        error = result.get("error") if isinstance(result, dict) else f"it returned a {type(result).__name__}"
        c.fail(f"{tool.__name__} returns data", f"{error}. Return what the query returns.")


async def exercise_2(c: Checklist) -> None:
    from google.adk.agents import LlmAgent

    module = marketing_module()
    c.check(len(module.DESCRIPTION.strip()) >= 30, "DESCRIPTION says what the agent is good at",
            "It's the pitch the orchestrator reads when it decides who should answer a question.")
    try:
        agent = module.build(get_services(), "gemini/not-called")
    except NotImplementedError:
        c.fail("build() returns an agent", "build() still raises NotImplementedError.")
        return
    except Exception as exc:  # noqa: BLE001
        c.fail("build() returns an agent", f"{type(exc).__name__}: {exc}")
        return
    if not c.check(isinstance(agent, LlmAgent), "build() returns an LlmAgent"):
        return
    c.check(agent.name == "marketing_agent", "The agent is named marketing_agent",
            f"It is named {agent.name!r}. The orchestrator calls it by this name.")
    c.check(agent.description == module.DESCRIPTION and bool(agent.description), "The agent uses DESCRIPTION")
    c.check(bool(agent.instruction), "The agent has an instruction",
            "Tell it how to behave. my_agent/prompts/marketing_agent.md is ready for you.")
    wanted = your_tools(module) + list(getattr(module, "READY_MADE_TOOLS", []))
    missing = [f.__name__ for f in wanted if f not in agent.tools]
    c.check(not missing, f"The agent has all {len(wanted)} tools",
            f"Missing: {', '.join(missing)}. Pass your tools and *READY_MADE_TOOLS in tools=[...].")


async def exercise_3(c: Checklist) -> None:
    from .agents import SPECIALISTS
    from .agents.common import prompt_path, walk_agents

    if not c.check("marketing_agent" in [m.NAME for m in SPECIALISTS], "marketing_agent is in SPECIALISTS",
                   "Add it to the list in my_agent/team.py. The orchestrator only knows the agents in that list."):
        return
    root = build_tree(c)
    if root is None:
        return
    c.check("marketing_agent" in {a.name for a in walk_agents(root)}, "The orchestrator can call marketing_agent")
    prompt = prompt_path("orchestrator").read_text()
    c.check("marketing_agent" in prompt, "The orchestrator's prompt mentions marketing_agent",
            "Add it to the list of specialists, with a line on what it covers.")
    c.check(GAP_HEADING not in prompt, "The orchestrator no longer says campaigns aren't covered",
            f"Delete the `{GAP_HEADING}` section in my_agent/prompts/orchestrator.md.")


def build_tree(c: Checklist):
    from .agents import build_root_agent

    try:
        return build_root_agent()
    except NotImplementedError:
        c.fail("The agents build", "marketing_agent's build() isn't finished yet. Do exercise 2 first.")
        return None


# ---------------------------------------------------------------------------
EXERCISES = {0: exercise_0, 1: exercise_1, 2: exercise_2, 3: exercise_3}


async def main_async(number: int) -> int:
    c = Checklist()
    print(f"Exercise {number}")
    try:
        await EXERCISES[number](c)
    except Exception as exc:  # noqa: BLE001 - e.g. a syntax error in marketing_agent.py
        c.fail("The code loads", f"{type(exc).__name__}: {exc}")
    finally:
        await get_services().database().close()
    print(f"\n{'All good. On to the next exercise.' if not c.failed else f'{c.failed} thing(s) to fix.'}")
    return 1 if c.failed else 0


def main() -> None:
    if len(sys.argv) != 2 or not sys.argv[1].isdigit() or int(sys.argv[1]) not in EXERCISES:
        print(f"Usage: make check-N, where N is one of {sorted(EXERCISES)}")
        sys.exit(2)
    sys.exit(asyncio.run(main_async(int(sys.argv[1]))))


if __name__ == "__main__":
    main()
