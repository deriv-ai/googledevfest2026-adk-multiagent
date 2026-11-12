"""`make check-N`: the per-exercise checklist works on a half-done and a finished agent."""

from types import ModuleType

import pytest
from google.adk.agents import LlmAgent

from devfest_agents import check
from my_agent import marketing_agent


async def campaign_tool(start_date: str, end_date: str, entity_id: str | None = None) -> dict:
    """Spend, clicks and sign-ups per campaign for a date range, one row per campaign."""
    return {"row_count": 1, "truncated": False, "rows": [{"spend_usd": 1.0}]}


async def channel_tool(start_date, end_date) -> dict:
    return {"error": "No value passed for :entity_id"}


def fake_module(*tools, description="Answers questions about ad campaigns and their sign-ups.", build=None):
    module = ModuleType("fake_marketing_agent")
    for tool in tools:
        tool.__module__ = module.__name__
        setattr(module, tool.__name__, tool)
    module.DESCRIPTION = description
    module.build = build or (lambda services, model: LlmAgent(name="marketing_agent", model=model, description=description,
                                                              instruction="Answer.", tools=list(tools)))
    return module


async def run_exercise(number, monkeypatch, module, capsys):
    monkeypatch.setattr(check, "marketing_module", lambda: module)
    c = check.Checklist()
    await check.EXERCISES[number](c)
    return c.failed, capsys.readouterr().out


def unfinished_build(services, model):
    raise NotImplementedError("marketing_agent.build() is exercise 2")


async def test_the_start_state_fails_exercises_1_and_2_with_hints(fake_services, monkeypatch, capsys):
    stub = fake_module(description="", build=unfinished_build)
    failed, out = await run_exercise(1, monkeypatch, stub, capsys)
    assert failed == 1 and "at least two tools (found 0)" in out
    failed, out = await run_exercise(2, monkeypatch, stub, capsys)
    assert failed == 2 and "still raises NotImplementedError" in out


async def test_exercise_1_explains_each_problem(fake_services, monkeypatch, capsys):
    failed, out = await run_exercise(1, monkeypatch, fake_module(campaign_tool, channel_tool), capsys)
    assert "campaign_tool returns data (1 rows" in out
    assert "channel_tool has a docstring" in out and "Add a type to: start_date, end_date" in out
    assert "No value passed for :entity_id" in out
    assert failed == 3


async def test_exercise_2_passes_a_finished_agent(fake_services, monkeypatch, capsys):
    failed, out = await run_exercise(2, monkeypatch, fake_module(campaign_tool, campaign_tool), capsys)
    assert failed == 0, out


async def test_exercise_3_needs_the_agent_in_specialists(fake_services, monkeypatch, capsys):
    from devfest_agents import agents

    monkeypatch.setattr(agents, "SPECIALISTS", [agents.finance_agent, agents.trading_agent])
    failed, out = await run_exercise(3, monkeypatch, marketing_agent, capsys)
    assert failed == 1 and "marketing_agent is in SPECIALISTS" in out


@pytest.mark.parametrize("arg", ["9", "x"])
def test_unknown_exercise_prints_usage(arg, monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["check", arg])
    with pytest.raises(SystemExit):
        check.main()
    assert "make check-N" in capsys.readouterr().out
