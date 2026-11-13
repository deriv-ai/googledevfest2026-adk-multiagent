"""Route tracing: ADK callbacks -> per-request event sink -> SSE.

``AgentTool`` runs its wrapped agent in a *nested* Runner, so the outer event
stream never shows what the orchestrator or the specialists did. Instead,
callbacks attached to every agent emit trace events into a sink stored in a
``contextvars.ContextVar``.

Why that works (verified by tests/test_tracing.py against ADK 2.13): the
runtime sets the sink in the context of the task that drives the turn. ADK
runs nested AgentTool runs in the same task, and parallel function calls in
child tasks created with ``asyncio.create_task`` / ``gather``, which copy the
current context. So every callback, at any depth, sees the same sink.

When no sink is set (e.g. under ``adk web``) the callbacks do nothing.
"""

from __future__ import annotations

import asyncio
import contextvars
import json
import time
from collections import OrderedDict
from typing import Any

from google.adk.tools.agent_tool import AgentTool
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.mcp_tool.mcp_tool import McpTool

PREVIEW_CHARS = 300


def now_ms() -> int:
    return int(time.time() * 1000)


class TraceSink:
    """Collects events for one chat turn and forwards them to an asyncio.Queue."""

    def __init__(self, queue: asyncio.Queue | None = None, root_agent: str = "main_agent"):
        self.queue = queue
        self.events: list[dict[str, Any]] = []
        self.route: list[str] = [root_agent]
        self._call_ids: dict[tuple, str] = {}
        self._call_started: dict[str, float] = {}
        self._finished: set[str] = set()
        self._agent_started: dict[tuple, float] = {}
        self._counter = 0
        # Event timestamps = wall clock at turn start + monotonic elapsed, so a
        # system-clock step mid-turn (e.g. a laptop VM resyncing after sleep)
        # can't reorder or stretch the route timeline.
        self._wall0 = now_ms()
        self._mono0 = time.perf_counter()

    def ts(self) -> int:
        return self._wall0 + int((time.perf_counter() - self._mono0) * 1000)

    def emit(self, event: dict[str, Any]) -> None:
        event.setdefault("ts", self.ts())
        self.events.append(event)
        if self.queue is not None:
            self.queue.put_nowait(event)

    def _add_route(self, node: str) -> None:
        if node not in self.route:
            self.route.append(node)

    # -- agents ---------------------------------------------------------------
    def agent_start(self, agent: str, invocation_id: str) -> None:
        self._agent_started[(agent, invocation_id)] = time.perf_counter()
        self._add_route(agent)
        self.emit({"type": "agent_start", "agent": agent, "invocation_id": invocation_id})

    def agent_end(self, agent: str, invocation_id: str) -> None:
        started = self._agent_started.pop((agent, invocation_id), None)
        ms = int((time.perf_counter() - started) * 1000) if started else None
        self.emit({"type": "agent_end", "agent": agent, "invocation_id": invocation_id, "ms": ms})

    # -- tools ----------------------------------------------------------------
    def tool_call(self, key: tuple, agent: str, tool: str, args: dict[str, Any], kind: str) -> str:
        self._counter += 1
        call_id = f"c{self._counter}"
        self._call_ids[key] = call_id
        self._call_started[call_id] = time.perf_counter()
        self._add_route(tool)
        self.emit({"type": "tool_call", "agent": agent, "tool": tool, "call_id": call_id,
                   "args": _jsonable(args), "kind": kind})
        return call_id

    def tool_result(self, key: tuple, agent: str, tool: str, kind: str, response: Any = None,
                    error: str | None = None) -> None:
        call_id = self._call_ids.get(key)
        if call_id is None:  # result without a recorded call (should not happen)
            self._counter += 1
            call_id = f"c{self._counter}"
        if call_id in self._finished:
            return
        self._finished.add(call_id)
        started = self._call_started.pop(call_id, None)
        ms = int((time.perf_counter() - started) * 1000) if started else None
        row_count = None
        if error is None:
            error = _error_of(response)
        if error is None and isinstance(response, dict):
            rc = response.get("row_count")
            row_count = rc if isinstance(rc, int) else None
        self.emit({
            "type": "tool_result", "agent": agent, "tool": tool, "call_id": call_id, "ms": ms, "kind": kind,
            "ok": error is None, "row_count": row_count, "error": error,
            "preview": _preview(response) if error is None else None,
        })


_current_sink: contextvars.ContextVar[TraceSink | None] = contextvars.ContextVar("trace_sink", default=None)


def current_sink() -> TraceSink | None:
    return _current_sink.get()


def set_sink(sink: TraceSink | None) -> contextvars.Token:
    return _current_sink.set(sink)


def reset_sink(token: contextvars.Token) -> None:
    _current_sink.reset(token)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def tool_kind(tool: Any) -> str:
    if isinstance(tool, AgentTool):
        return "agent"
    if isinstance(tool, McpTool):
        return "mcp"
    tool_type = getattr(tool, "tool_type", None)
    if tool_type in ("sql", "factual"):
        return tool_type
    return "function"


def _jsonable(value: Any) -> Any:
    try:
        json.dumps(value)
        return value
    except TypeError:
        return json.loads(json.dumps(value, default=str))


def _error_of(response: Any) -> str | None:
    if isinstance(response, dict):
        err = response.get("error")
        if err:
            return str(err)
    return None


def _preview(response: Any) -> str | None:
    if response is None:
        return None
    if isinstance(response, str):
        text = response
    elif isinstance(response, dict):
        if "result" in response and len(response) == 1 and isinstance(response["result"], str):
            text = response["result"]
        elif "rows" in response:
            text = json.dumps(response.get("rows", [])[:5], default=str)
        elif "answer" in response:
            text = str(response.get("answer"))
        else:
            text = json.dumps(response, default=str)
    else:
        text = str(response)
    text = " ".join(text.split())
    return text[:PREVIEW_CHARS] + ("..." if len(text) > PREVIEW_CHARS else "")


def _key(tool: Any, tool_context: Any) -> tuple:
    return (getattr(tool_context, "invocation_id", None), getattr(tool_context, "function_call_id", None),
            getattr(tool, "name", None))


# ---------------------------------------------------------------------------
# ADK callbacks (parameter names matter: ADK passes them as keywords)
# ---------------------------------------------------------------------------
def before_agent(callback_context) -> None:
    sink = current_sink()
    if sink is not None:
        sink.agent_start(callback_context.agent_name, callback_context.invocation_id)
    return None


def after_agent(callback_context) -> None:
    sink = current_sink()
    if sink is not None:
        sink.agent_end(callback_context.agent_name, callback_context.invocation_id)
    return None


def before_tool(tool, args, tool_context) -> None:
    sink = current_sink()
    if sink is not None:
        sink.tool_call(_key(tool, tool_context), tool_context.agent_name, tool.name, dict(args or {}),
                       tool_kind(tool))
    return None


def after_tool(tool, args, tool_context, tool_response) -> None:
    sink = current_sink()
    if sink is not None:
        sink.tool_result(_key(tool, tool_context), tool_context.agent_name, tool.name, tool_kind(tool),
                         response=tool_response)
    return None


def on_tool_error(tool, args, tool_context, error) -> dict[str, Any] | None:
    """Record the failure and fail soft: the model gets an error dict instead of
    the whole turn crashing (e.g. the database dropped mid-call). Unknown tool
    names (hallucinated calls) are left to ADK's own not-found response."""
    message = f"{type(error).__name__}: {error}"[:500]
    sink = current_sink()
    if sink is not None:
        sink.tool_result(_key(tool, tool_context), tool_context.agent_name, getattr(tool, "name", "?"),
                         tool_kind(tool), error=message)
    if type(tool) is BaseTool:  # ADK's placeholder for an unknown tool name
        return None
    return {"error": f"The tool {getattr(tool, 'name', '?')} failed ({message}). "
                     "Tell the user this part could not be answered."}


class _CallCounter:
    """Counts calls per key, forgetting the oldest keys so it can't grow forever."""

    def __init__(self) -> None:
        self._counts: OrderedDict[Any, int] = OrderedDict()

    def bump(self, key: Any) -> int:
        count = self._counts.get(key, 0) + 1
        self._counts[key] = count
        self._counts.move_to_end(key)
        while len(self._counts) > 1000:
            self._counts.popitem(last=False)
        return count


class DelegationGuard:
    """before_tool_callback capping AgentTool delegations per agent invocation
    (one orchestrator turn) and blocking self-recursion. Returning a dict skips
    the tool; ADK then sends that dict to the model as the tool result."""

    def __init__(self, max_delegations: int):
        self.max_delegations = max_delegations
        self._counter = _CallCounter()

    def __call__(self, tool, args, tool_context) -> dict[str, Any] | None:
        if not isinstance(tool, AgentTool):
            return None
        if tool.name == tool_context.agent_name:
            return {"error": f"{tool.name} cannot delegate to itself."}
        if self._counter.bump(tool_context.invocation_id) > self.max_delegations:
            return {"error": f"Delegation limit reached ({self.max_delegations} specialist calls per question). "
                             "Answer with the findings you already have and say what is missing."}
        return None


class ToolCallLimit:
    """before_tool_callback capping how many tools one specialist calls for one
    request, so a model stuck in a loop answers instead of running for minutes."""

    def __init__(self, max_calls: int):
        self.max_calls = max_calls
        self._counter = _CallCounter()

    def __call__(self, tool, args, tool_context) -> dict[str, Any] | None:
        if isinstance(tool, AgentTool):
            return None
        if self._counter.bump((tool_context.invocation_id, tool_context.agent_name)) > self.max_calls:
            return {"error": f"Tool-call limit reached ({self.max_calls} calls per request). "
                             "Answer now with the results you already have."}
        return None


def attach(agent, *, guard: DelegationGuard | ToolCallLimit | None = None) -> None:
    """Add tracing (and optionally a call limit) to an LlmAgent.

    Callbacks the agent already has are kept and run after ours.
    """
    agent.before_agent_callback = _first(agent.before_agent_callback, before_agent)
    agent.after_agent_callback = _first(agent.after_agent_callback, after_agent)
    # Order matters: trace first so a blocked call still shows as a tool_call;
    # ADK still runs after_tool callbacks on the guard's dict, closing it.
    agent.before_tool_callback = _first(agent.before_tool_callback, before_tool, *([guard] if guard else []))
    agent.after_tool_callback = _first(agent.after_tool_callback, after_tool)
    agent.on_tool_error_callback = _first(agent.on_tool_error_callback, on_tool_error)


def _first(existing, *ours) -> list:
    """Our callbacks, then the agent's own (ADK allows one callable, a list, or None)."""
    existing = [] if existing is None else existing if isinstance(existing, list) else [existing]
    return [*ours, *(callback for callback in existing if callback not in ours)]
