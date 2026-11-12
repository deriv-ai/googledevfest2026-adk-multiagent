"""Check one workshop exercise: python -m devfest_agents.check <0-4>

Prints a checklist with a tick or a cross per item, and a hint for every cross.
Exercises 2, 3 and 4 also ask real questions, so they need the LLM key.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import sys
from typing import Any

import yaml

from .config import REPO_ROOT
from .evals import NO, OK, ask, grade, missed_checks
from .runtime import AgentRuntime
from .services import get_services
from .tools.sql_query import run_sql

PRACTICE = REPO_ROOT / "evals" / "practice.yaml"
SAMPLE_ARGS = {"start_date": "2026-07-01", "end_date": "2026-09-30"}
GAP_HEADING = "## Not covered yet"  # in my_agent/prompts/orchestrator.md until exercise 3

# Exercise 1: the two data-team queries participants wrap themselves.
YOUR_QUERIES = {"fetch_campaign_performance": "one row per campaign",
                "fetch_channel_summary": "one row per ad channel"}

# Exercise 2: one question for the marketing agent on its own. Not in either eval set.
SMOKE_QUESTION = {"id": "check-2", "question": "How many new clients did our ad campaigns bring in during August 2026?",
                  "agents": [], "numbers": [19]}

# Exercise 4: the two kinds of teamwork, and a tie-break. The sequential question's second
# request has to use what the first answer found: the entity with the most sign-ups.
PARALLEL = ("spend-per-new-client", "marketing_agent", "trading_agent")
SEQUENTIAL = ("top-signup-entity-commission", "marketing_agent", "trading_agent", ("NM-INTL", "International"))
TIE_BREAK = "sg-marketing-booked"


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
            "Add GEMINI_API_KEY to .env, then run `make up` again.")
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
        c.fail(f"{tool.__name__} returns data", f"{error}. Return what the data team's query returns.")


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
    if not c.failed:
        await smoke_test(c, module)


async def smoke_test(c: Checklist, module) -> None:
    """Ask the marketing agent one question on its own, with no orchestrator in between."""
    from . import tracing
    from .agents.model import agent_model

    settings = get_services().settings
    if not settings.llm_key_configured:
        c.fail("Your agent answers a question", "Add an LLM key to .env first.")
        return
    agent = module.build(get_services(), agent_model(settings))
    tracing.attach(agent)
    print(f"  Asking your agent on its own: \"{SMOKE_QUESTION['question']}\"")
    events = await ask(AgentRuntime(agent, settings=settings), SMOKE_QUESTION)
    calls = [f"{e['tool']}({', '.join(f'{k}={v!r}' for k, v in e.get('args', {}).items())})"
             for e in events if e["type"] == "tool_call"]
    if not c.check(bool(calls), f"It picked a tool: {'; '.join(calls[:3])}" if calls else "It picked a tool",
                   "It answered without calling a tool. Make the docstrings say what each tool returns."):
        return
    answer = events[-1].get("text", "") if events[-1]["type"] == "answer" else ""
    c.check(bool(answer) and not missed_checks(SMOKE_QUESTION, answer), "It found the right answer (19 new clients)",
            events[-1].get("message") or f"It said: {answer[:200]}")
    print("  That tested your agent on its own. The chat can't reach it until exercise 3.")


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
    print("  One more question, different from the one you asked in the chat, for extra coverage:")
    await check_live(c, root, ["signups-october"])


async def exercise_4(c: Checklist) -> None:
    root = build_tree(c)
    if root is None:
        return
    if not get_services().settings.llm_key_configured:
        c.fail("Live questions", "Add an LLM key to .env first.")
        return
    questions = practice_questions()
    ids = [PARALLEL[0], SEQUENTIAL[0], TIE_BREAK]
    runtime = AgentRuntime(root)
    print("  Asking three questions (about a minute)...")
    events_by_id = dict(zip(ids, await asyncio.gather(*(ask(runtime, questions[i]) for i in ids))))
    results = {i: await grade(questions[i], events_by_id[i]) for i in ids}

    question_id, first, second = PARALLEL
    if check_result(c, results[question_id], "in parallel"):
        c.check(ran_in_parallel(events_by_id[question_id], first, second),
                f"{first} and {second} were asked in the same step",
                "They don't depend on each other, so the orchestrator should ask both at once.")

    question_id, first, second, handoff = SEQUENTIAL
    if check_result(c, results[question_id], "one after the other"):
        request = first_call(events_by_id[question_id], second)
        c.check(ran_in_order(events_by_id[question_id], first, second)
                and any(word in json.dumps(request) for word in handoff),
                f"{second} was asked only after {first} answered, about the entity {first} found",
                "The second question depends on the first answer. Ask one, read it, then ask the other.")

    check_result(c, results[TIE_BREAK], "")


def check_result(c: Checklist, r: dict[str, Any], how: str) -> bool:
    """Route and answer of one live question. True when both are right."""
    agents = " and ".join(r["expected_agents"]) + (f", {how}" if how else "")
    routed = c.check(r["route_point"] == 1, f"'{r['question']}' goes to {agents}",
                     r["error"] or f"It went to {', '.join(r['called_agents']) or 'no agent'}. "
                                   "Sharpen the routing rules.")
    answered = c.check(r["answer_point"] == 1, "...and the answer is right",
                       r["error"] or "; ".join(r["missing"]))
    return routed and answered


def orchestrator_steps(events: list[dict[str, Any]], agent: str, kind: str) -> list[int]:
    return [i for i, e in enumerate(events) if e["type"] == kind and e.get("agent") == "orchestrator"
            and e.get("tool") == agent]


def ran_in_parallel(events: list[dict[str, Any]], a: str, b: str) -> bool:
    """Both calls went out before either answer came back: one step, not two."""
    calls = orchestrator_steps(events, a, "tool_call")[:1] + orchestrator_steps(events, b, "tool_call")[:1]
    results = orchestrator_steps(events, a, "tool_result") + orchestrator_steps(events, b, "tool_result")
    return len(calls) == 2 and bool(results) and max(calls) < min(results)


def ran_in_order(events: list[dict[str, Any]], first: str, second: str) -> bool:
    """The second agent was first asked after the first agent had answered."""
    first_results = orchestrator_steps(events, first, "tool_result")
    second_calls = orchestrator_steps(events, second, "tool_call")
    return bool(first_results and second_calls) and first_results[0] < second_calls[0]


def first_call(events: list[dict[str, Any]], agent: str) -> dict[str, Any]:
    calls = orchestrator_steps(events, agent, "tool_call")
    return events[calls[0]].get("args", {}) if calls else {}


def practice_questions() -> dict[str, dict[str, Any]]:
    return {q["id"]: q for q in yaml.safe_load(PRACTICE.read_text())}


def build_tree(c: Checklist):
    from .agents import build_root_agent

    try:
        return build_root_agent()
    except NotImplementedError:
        c.fail("The agents build", "marketing_agent's build() isn't finished yet. Do exercise 2 first.")
        return None


async def check_live(c: Checklist, root, ids: list[str]) -> None:
    if not get_services().settings.llm_key_configured:
        c.fail("Live questions", "Add an LLM key to .env first.")
        return
    questions = practice_questions()
    runtime = AgentRuntime(root)
    all_events = await asyncio.gather(*(ask(runtime, questions[i]) for i in ids))
    for question_id, events in zip(ids, all_events):
        r = await grade(questions[question_id], events)
        c.check(r["route_point"] == 1, f"'{r['question']}' goes to {', '.join(r['expected_agents'])}",
                r["error"] or f"It went to {', '.join(r['called_agents']) or 'no agent'}. "
                              "Sharpen the descriptions and routing rules.")


# ---------------------------------------------------------------------------
EXERCISES = {0: exercise_0, 1: exercise_1, 2: exercise_2, 3: exercise_3, 4: exercise_4}


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
