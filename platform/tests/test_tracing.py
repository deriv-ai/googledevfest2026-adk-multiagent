"""Tracing through the real agent tree with scripted (fake) LLMs.

Proves that callback events from agents nested inside AgentTool (two levels
deep) and from parallel function calls all reach the per-request sink held in
a ContextVar - the mechanism the live Agent Route panel relies on.
"""

import asyncio

from devfest_agents.agents import build_root_agent
from devfest_agents.agents.common import walk_agents
from devfest_agents.runtime import AgentRuntime

from .helpers import ScriptedLlm, call, text


def agents_by_name(root):
    return {agent.name: agent for agent in walk_agents(root)}


def main_script(req, seen):
    return [call("orchestrator", request="Top instrument in Oct 2026, monthly P&L Q3, and campaign spend")] \
        if seen == 0 else [text("**Final answer** from main_agent")]


def orchestrator_script(req, seen):
    if seen == 0:  # independent -> parallel in ONE response
        return [call("finance_agent", request="Monthly P&L Jul-Sep 2026"),
                call("trading_agent", request="Top instrument by commission Oct 2026")]
    if seen == 2:  # dependent -> sequential follow-up
        return [call("marketing_agent", request="Spend per channel Jul-Sep 2026")]
    return [text("Finance: ... Trading: ... Marketing: ...")]


def finance_script(req, seen):
    return [call("finance_monthly_pnl", start_month="2026-07-01", end_month="2026-09-01")] if seen == 0 \
        else [text("Finance numbers")]


def trading_script(req, seen):
    return [call("trading_top_instruments", start_date="2026-10-01", end_date="2026-10-31", metric="commission")] \
        if seen == 0 else [text("BTCUSD (Bitcoin) led commission")]


def marketing_script(req, seen):
    return [call("channel_summary", start_date="2026-07-01", end_date="2026-09-30")] if seen == 0 \
        else [text("Search ads spent the most")]


SCRIPTS = {"main_agent": main_script, "orchestrator": orchestrator_script, "finance_agent": finance_script,
           "trading_agent": trading_script, "marketing_agent": marketing_script}


def build_tree(services, scripts=SCRIPTS, **llm_kwargs):
    root = build_root_agent(services, model_factory=lambda role: ScriptedLlm(model="fake", responder=main_script))
    for name, agent in agents_by_name(root).items():
        agent.model = ScriptedLlm(model=f"fake-{name}", responder=scripts[name], **llm_kwargs)
    return root


async def collect(runtime, question="q", conversation_id="conv-1", **kw):
    return [e async for e in runtime.ask_stream(conversation_id, question, **kw)]


async def test_nested_and_parallel_events_reach_sink(fake_services):
    runtime = AgentRuntime(build_tree(fake_services), settings=fake_services.settings)
    events = await collect(runtime)
    types_ = [e["type"] for e in events]
    assert types_[0] == "start" and types_[-1] == "answer", types_

    starts = [e["agent"] for e in events if e["type"] == "agent_start"]
    assert set(starts) == {"main_agent", "orchestrator", "finance_agent", "trading_agent", "marketing_agent"}
    assert {e["agent"] for e in events if e["type"] == "agent_end"} == set(starts)

    calls = {e["tool"]: e for e in events if e["type"] == "tool_call"}
    results = {e["tool"]: e for e in events if e["type"] == "tool_result"}
    assert set(calls) == set(results) == {"orchestrator", "finance_agent", "trading_agent", "marketing_agent",
                                          "finance_monthly_pnl", "trading_top_instruments", "channel_summary"}

    # delegation edges vs leaf tools
    assert calls["orchestrator"]["agent"] == "main_agent" and calls["orchestrator"]["kind"] == "agent"
    assert calls["finance_agent"]["agent"] == "orchestrator" and calls["finance_agent"]["kind"] == "agent"
    assert calls["finance_monthly_pnl"]["agent"] == "finance_agent" and calls["finance_monthly_pnl"]["kind"] == "sql"
    assert calls["trading_top_instruments"]["args"]["metric"] == "commission"
    assert calls["channel_summary"]["agent"] == "marketing_agent" and calls["channel_summary"]["kind"] == "function"
    assert results["channel_summary"]["row_count"] == 1 and results["channel_summary"]["ok"]
    assert results["trading_top_instruments"]["row_count"] == 2 and results["trading_top_instruments"]["ok"]
    assert results["finance_agent"]["preview"] == "Finance numbers"
    assert all(isinstance(r["ms"], int) for r in results.values())

    # call ids are unique and pair calls with results
    ids = [e["call_id"] for e in events if e["type"] == "tool_call"]
    assert len(ids) == len(set(ids))
    for name in calls:
        assert calls[name]["call_id"] == results[name]["call_id"]

    # parallel: both specialist calls happen before either result
    pos = {(e["type"], e.get("tool")): i for i, e in enumerate(events)}
    first_result = min(pos[("tool_result", "finance_agent")], pos[("tool_result", "trading_agent")])
    assert pos[("tool_call", "finance_agent")] < first_result
    assert pos[("tool_call", "trading_agent")] < first_result
    # ...and their leaf tools overlap in time
    assert pos[("tool_call", "trading_top_instruments")] < pos[("tool_result", "finance_monthly_pnl")]
    # sequential: marketing is called only after both specialists returned
    assert pos[("tool_call", "marketing_agent")] > max(pos[("tool_result", "finance_agent")],
                                                  pos[("tool_result", "trading_agent")])

    answer = events[-1]
    assert answer["text"] == "**Final answer** from main_agent"
    assert answer["route"][:2] == ["main_agent", "orchestrator"]
    assert {"finance_agent", "trading_agent", "marketing_agent", "trading_top_instruments"} <= set(answer["route"])
    assert isinstance(answer["elapsed_ms"], int)
    assert all("ts" in e for e in events)


async def test_concurrent_turns_have_isolated_sinks(fake_services):
    runtime = AgentRuntime(build_tree(fake_services), settings=fake_services.settings)
    a, b = await asyncio.gather(collect(runtime, conversation_id="a"), collect(runtime, conversation_id="b"))
    for events in (a, b):
        assert sum(1 for e in events if e["type"] == "agent_start" and e["agent"] == "main_agent") == 1
        assert sum(1 for e in events if e["type"] == "tool_call" and e["tool"] == "finance_monthly_pnl") == 1


async def test_delegation_cap_blocks_extra_calls(fake_services):
    fake_services.settings.max_delegations = 2

    def greedy(req, seen):
        if seen == 0:
            return [call("finance_agent", request=f"q{i}") for i in range(3)]
        return [text("merged")]

    root = build_tree(fake_services, scripts=dict(SCRIPTS, orchestrator=greedy))
    events = await collect(AgentRuntime(root, settings=fake_services.settings))
    fin_results = [e for e in events if e["type"] == "tool_result" and e["tool"] == "finance_agent"]
    assert len(fin_results) == 3
    blocked = [e for e in fin_results if not e["ok"]]
    assert len(blocked) == 1 and "Delegation limit" in blocked[0]["error"]
    assert sum(1 for e in events if e["type"] == "agent_start" and e["agent"] == "finance_agent") == 2
    assert events[-1]["type"] == "answer"


async def test_orchestrator_instruction_has_live_catalogue(fake_services):
    from devfest_agents.agents.orchestrator import build_catalogue
    from devfest_agents.tools.spec import ToolSpec

    from .helpers import KPI_FACTUAL

    agents = agents_by_name(build_tree(fake_services))
    specialists = [agents[name] for name in ("finance_agent", "trading_agent", "marketing_agent")]
    cat = await build_catalogue(specialists)
    assert "`finance_monthly_pnl`: Monthly P&L" in cat and "`trading_top_instruments`" in cat
    assert "`channel_summary`: Spend per ad channel for a date range." in cat
    await fake_services.repo.create(ToolSpec.model_validate(KPI_FACTUAL))
    assert "`kpi_definitions`: KPI definitions (curated answer)" in await build_catalogue(specialists)


def test_attach_keeps_the_agents_own_callbacks():
    from google.adk.agents import LlmAgent

    from devfest_agents import tracing

    def mine(tool, args, tool_context):
        return None

    agent = LlmAgent(name="a", model="gemini/x", before_tool_callback=mine)
    tracing.attach(agent)
    tracing.attach(agent)  # building twice must not stack our callbacks either
    assert agent.before_tool_callback == [tracing.before_tool, mine]
    assert agent.after_agent_callback[0] is tracing.after_agent
