"""`make check-N`: the per-exercise checklist works on a half-done and a finished agent."""

import inspect
from types import ModuleType

import pytest
from google.adk.agents import LlmAgent

from devfest_agents import check
from my_agent import marketing_agent
from my_agent import marketing_queries as queries


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


async def test_exercise_2_passes_a_finished_agent_without_the_llm(fake_services, monkeypatch, capsys):
    pitch = "Answers questions about ad campaigns and their sign-ups."
    tools_only_yours = fake_module(campaign_tool, description=pitch, build=lambda s, m: LlmAgent(
        name="marketing_agent", model=m, description=pitch, instruction="Answer.", tools=[campaign_tool]))
    failed, out = await run_exercise(2, monkeypatch, tools_only_yours, capsys)
    assert failed == 1 and "Missing: ready_tool" in out

    def no_llm(*args, **kwargs):
        raise AssertionError("check-2 called the LLM")

    monkeypatch.setattr("devfest_agents.agents.model.agent_model", no_llm)
    failed, out = await run_exercise(2, monkeypatch, fake_module(campaign_tool), capsys)
    assert failed == 0, out


async def test_exercise_3_needs_the_agent_in_specialists(fake_services, monkeypatch, capsys):
    from devfest_agents import agents

    monkeypatch.setattr(agents, "SPECIALISTS", [agents.finance_agent, agents.trading_agent])
    failed, out = await run_exercise(3, monkeypatch, marketing_agent, capsys)
    assert failed == 1 and "marketing_agent is in SPECIALISTS" in out


def test_there_is_no_check_for_exercise_4():
    assert sorted(check.EXERCISES) == [0, 1, 2, 3]


def test_only_check_0_calls_the_llm_and_never_runs_the_agents():
    assert not hasattr(check, "check_live") and not hasattr(check, "smoke_test")
    assert "AgentRuntime" not in inspect.getsource(check)
    for number in (1, 2, 3):
        assert "ping_llm" not in inspect.getsource(check.EXERCISES[number])


@pytest.mark.parametrize("error, passed, says", [
    (None, True, "Your LLM key works"),
    ("RateLimitError: 429 RESOURCE_EXHAUSTED", True, "rate-limited"),
    ("AuthenticationError: API_KEY_INVALID", False, "The key was rejected"),
    ("AuthenticationError: 401 ACCESS_TOKEN_TYPE_UNSUPPORTED", False, "new keys start with AQ."),
    ("PermissionDeniedError: 403 PERMISSION_DENIED", False, "can't call the Gemini API"),
    ("DefaultCredentialsError: default credentials were not found", False, "Vertex AI model"),
    ("NotFoundError: 404 model not found", False, "can't use that model"),
])
async def test_exercise_0_tries_the_key(error, passed, says, fake_services, monkeypatch, capsys):
    async def ping(settings):
        return error

    async def data_loaded(*args, **kwargs):
        return {"rows": [{"n": 117}]}

    monkeypatch.setattr(check, "ping_llm", ping)
    monkeypatch.setattr(check, "run_sql", data_loaded)
    monkeypatch.setattr(type(fake_services.settings), "llm_key_configured", property(lambda self: True))
    c = check.Checklist()
    await check.exercise_0(c)
    out = capsys.readouterr().out
    assert says in out
    assert ("The key was rejected" not in out) if passed else (c.failed >= 1)


@pytest.mark.parametrize("arg", ["9", "4", "x"])
def test_unknown_exercise_prints_usage(arg, monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["check", arg])
    with pytest.raises(SystemExit):
        check.main()
    assert "make check-N" in capsys.readouterr().out
