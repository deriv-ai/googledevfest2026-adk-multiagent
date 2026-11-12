"""`make check-N`: the per-exercise checklist works on a half-done and a finished agent."""

from types import ModuleType

import pytest
from google.adk.agents import LlmAgent

from devfest_agents import check
from my_agent import marketing_agent
from my_agent import marketing_queries as queries

from .helpers import ScriptedLlm, call, text


async def campaign_tool(start_date: str, end_date: str, entity_id: str | None = None) -> dict:
    """Spend, clicks and sign-ups per campaign for a date range, one row per campaign."""
    return await queries.fetch_campaign_performance(start_date, end_date, entity_id)


async def channel_tool(start_date, end_date) -> dict:
    return await queries.fetch_channel_summary(start_date, end_date)


async def ready_tool(start_date: str, end_date: str) -> dict:
    """A ready-made tool that ships with the starter, so it doesn't count as the participant's."""
    return await queries.fetch_entity_summary(start_date, end_date)


def fake_module(*tools, description="Answers questions about ad campaigns and their sign-ups.", build=None,
                ready=(ready_tool,)):
    module = ModuleType("fake_marketing_agent")
    for tool in (*tools, *ready):
        tool.__module__ = module.__name__
        setattr(module, tool.__name__, tool)
    module.READY_MADE_TOOLS = list(ready)
    module.DESCRIPTION = description
    module.build = build or (lambda services, model: LlmAgent(name="marketing_agent", model=model, description=description,
                                                              instruction="Answer.", tools=[*tools, *ready]))
    return module


async def run_exercise(number, monkeypatch, module, capsys):
    monkeypatch.setattr(check, "marketing_module", lambda: module)
    c = check.Checklist()
    await check.EXERCISES[number](c)
    return c.failed, capsys.readouterr().out


async def test_the_start_state_fails_exercises_1_and_2_with_hints(fake_services, monkeypatch, capsys):
    failed, out = await run_exercise(1, monkeypatch, marketing_agent, capsys)
    assert failed == 2 and "A tool of yours calls queries.fetch_campaign_performance" in out
    assert "monthly_spend" not in out
    failed, out = await run_exercise(2, monkeypatch, marketing_agent, capsys)
    assert failed == 2 and "still raises NotImplementedError" in out


async def test_exercise_1_explains_each_problem(fake_services, monkeypatch, capsys):
    failed, out = await run_exercise(1, monkeypatch, fake_module(campaign_tool, channel_tool), capsys)
    assert "campaign_tool returns data" in out and "ready_tool" not in out
    assert "channel_tool has a docstring" in out and "Add a type to: start_date, end_date" in out
    assert failed == 2


async def test_exercise_2_wants_every_tool_then_asks_the_agent_alone(fake_services, monkeypatch, capsys):
    pitch = "Answers questions about ad campaigns and their sign-ups."
    tools_only_yours = fake_module(campaign_tool, description=pitch, build=lambda s, m: LlmAgent(
        name="marketing_agent", model=m, description=pitch, instruction="Answer.", tools=[campaign_tool]))
    failed, out = await run_exercise(2, monkeypatch, tools_only_yours, capsys)
    assert failed == 1 and "Missing: ready_tool" in out and "Asking your agent" not in out

    def respond(request, seen):
        if seen == 0:
            return [call("campaign_tool", start_date="2026-08-01", end_date="2026-08-31")]
        return [text("Our campaigns brought in 19 new clients in August 2026.")]

    monkeypatch.setattr("devfest_agents.agents.model.agent_model", lambda settings: ScriptedLlm(model="x", responder=respond))
    failed, out = await run_exercise(2, monkeypatch, fake_module(campaign_tool), capsys)
    assert failed == 0, out
    assert "It picked a tool: campaign_tool(start_date='2026-08-01', end_date='2026-08-31')" in out
    assert "It found the right answer" in out and "can't reach it until exercise 3" in out


async def test_exercise_3_needs_the_agent_in_specialists(fake_services, monkeypatch, capsys):
    from devfest_agents import agents

    monkeypatch.setattr(agents, "SPECIALISTS", [agents.finance_agent, agents.trading_agent])
    failed, out = await run_exercise(3, monkeypatch, marketing_agent, capsys)
    assert failed == 1 and "marketing_agent is in SPECIALISTS" in out


def events(*steps):
    """("call"|"result", agent) pairs as the orchestrator's tool events."""
    kind = {"call": "tool_call", "result": "tool_result"}
    return [{"type": kind[k], "agent": "orchestrator", "tool": tool, "args": {"request": f"about {tool}"}}
            for k, tool in steps]


def test_parallel_means_both_calls_before_either_answer():
    together = events(("call", "a"), ("call", "b"), ("result", "b"), ("result", "a"))
    one_then_other = events(("call", "a"), ("result", "a"), ("call", "b"), ("result", "b"))
    assert check.ran_in_parallel(together, "a", "b")
    assert not check.ran_in_parallel(one_then_other, "a", "b")
    assert not check.ran_in_parallel(events(("call", "a"), ("result", "a")), "a", "b")


def test_sequential_means_the_second_call_waits_for_the_first_answer():
    one_then_other = events(("call", "a"), ("result", "a"), ("call", "b"), ("result", "b"))
    together = events(("call", "a"), ("call", "b"), ("result", "a"), ("result", "b"))
    assert check.ran_in_order(one_then_other, "a", "b")
    assert not check.ran_in_order(together, "a", "b")
    assert check.first_call(one_then_other, "b") == {"request": "about b"}


@pytest.mark.parametrize("arg", ["9", "x"])
def test_unknown_exercise_prints_usage(arg, monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["check", arg])
    with pytest.raises(SystemExit):
        check.main()
    assert "make check-N" in capsys.readouterr().out
