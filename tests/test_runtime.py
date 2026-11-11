from devfest_agents.config import Settings
from devfest_agents.runtime import MISSING_KEY_MESSAGE, AgentRuntime

from .helpers import ScriptedLlm, text
from .test_tracing import SCRIPTS, agents_by_name, build_tree, collect


async def test_missing_key_returns_error_event(fake_services):
    settings = Settings(_env_file=None)
    runtime = AgentRuntime(agent_factory=lambda: (_ for _ in ()).throw(AssertionError("must not build")),
                           settings=settings)
    events = await collect(runtime)
    assert [e["type"] for e in events] == ["start", "error"]
    assert events[1]["message"] == MISSING_KEY_MESSAGE


async def test_failed_turn_rolls_back_session(fake_services):
    root = build_tree(fake_services)
    runtime = AgentRuntime(root, settings=fake_services.settings)
    ok = await collect(runtime, conversation_id="c1")
    assert ok[-1]["type"] == "answer"
    session = await runtime.session_service.get_session(app_name="nimbus", user_id="web", session_id="c1")
    n_events = len(session.events)

    # The root model fails after the orchestrator already ran: tool events were
    # appended to the session, and must all be rolled back.
    root.model = ScriptedLlm(model="x", responder=SCRIPTS["main_agent"], fail_after=1)
    bad = await collect(runtime, conversation_id="c1")
    assert bad[-1]["type"] == "error"
    assert "scripted model failure" in bad[-1]["message"]
    assert any(e["type"] == "tool_result" and e["tool"] == "orchestrator" for e in bad)
    session = await runtime.session_service.get_session(app_name="nimbus", user_id="web", session_id="c1")
    assert len(session.events) == n_events  # rolled back


async def test_tool_errors_fail_soft(fake_services):
    root = build_tree(fake_services)
    agents_by_name(root)["marketing_agent"].model = ScriptedLlm(model="x", responder=SCRIPTS["marketing_agent"],
                                                                fail=True)
    events = await collect(AgentRuntime(root, settings=fake_services.settings))
    failed = [e for e in events if e["type"] == "tool_result" and e["tool"] == "marketing_agent"]
    assert len(failed) == 1 and failed[0]["ok"] is False
    assert events[-1]["type"] == "answer"


async def test_keepalive_pings(fake_services):
    slow = {**SCRIPTS, "main_agent": lambda req, seen: [text("hi")]}
    root = build_tree(fake_services, scripts=slow, delay=0.3)
    events = await collect(AgentRuntime(root, settings=fake_services.settings), keepalive_seconds=0.05)
    assert any(e["type"] == "ping" for e in events)
    assert events[-1]["type"] == "answer" and events[-1]["text"] == "hi"
    assert events[-1]["route"] == ["main_agent"]


async def test_reset_forgets_conversation(fake_services):
    runtime = AgentRuntime(build_tree(fake_services), settings=fake_services.settings)
    await collect(runtime, conversation_id="r1")
    await runtime.reset("r1")
    assert await runtime.session_service.get_session(app_name="nimbus", user_id="web", session_id="r1") is None
    await runtime.reset("never-existed")
