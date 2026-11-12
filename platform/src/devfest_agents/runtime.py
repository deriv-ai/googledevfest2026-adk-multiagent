"""Chat runtime: one ADK Runner + InMemorySessionService, keyed by conversation id.

``ask_stream()`` runs a turn as its own asyncio task (with a TraceSink set in
that task's context) and yields contract events as they arrive:

    start -> agent_start / tool_call / tool_result / agent_end / answer_delta ... -> answer | error

answer_delta carries the next chunk of the main agent's answer as the model writes
it (ADK SSE streaming); answer then carries the whole text.

plus ``{"type": "ping"}`` keepalives while nothing else happens. If the turn
fails, the session is rolled back to its state before the turn so the next
question doesn't inherit a half-finished tool exchange.
"""

from __future__ import annotations

import asyncio
import contextvars
import copy
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from . import tracing
from .config import Settings, get_settings

logger = logging.getLogger(__name__)

APP_NAME = "nimbus"
USER_ID = "web"
KEEPALIVE_SECONDS = 15.0
# Stream the main agent's tokens. Agents behind an AgentTool still run unary (ADK forces it).
STREAMING = RunConfig(streaming_mode=StreamingMode.SSE)

MISSING_KEY_MESSAGE = (
    "No LLM key is configured. Add LLM_API_KEY (and AGENT_MODEL) to .env "
    "as step 2 of Set up in README.md shows, then run make up again."
)


class AgentRuntime:
    def __init__(self, root_agent=None, *, settings: Settings | None = None, require_key: bool = True,
                 agent_factory=None):
        self.settings = settings or get_settings()
        self.require_key = require_key
        self._root_agent = root_agent
        self._agent_factory = agent_factory
        self._runner: Runner | None = None
        self.session_service = InMemorySessionService()
        self._locks: dict[str, asyncio.Lock] = {}

    # -- lazy construction ------------------------------------------------------
    @property
    def root_agent(self):
        if self._root_agent is None:
            if self._agent_factory is not None:
                self._root_agent = self._agent_factory()
            else:
                from .agents import build_root_agent

                self._root_agent = build_root_agent()
        return self._root_agent

    @property
    def runner(self) -> Runner:
        if self._runner is None:
            self._runner = Runner(app_name=APP_NAME, agent=self.root_agent, session_service=self.session_service)
        return self._runner

    # -- sessions ---------------------------------------------------------------
    async def _get_or_create_session(self, conversation_id: str):
        session = await self.session_service.get_session(app_name=APP_NAME, user_id=USER_ID,
                                                         session_id=conversation_id)
        if session is None:
            session = await self.session_service.create_session(app_name=APP_NAME, user_id=USER_ID,
                                                                session_id=conversation_id)
        return session

    async def _rollback(self, before) -> None:
        """Restore the session to its pre-turn snapshot."""
        try:
            await self.session_service.delete_session(app_name=APP_NAME, user_id=USER_ID, session_id=before.id)
            restored = await self.session_service.create_session(
                app_name=APP_NAME, user_id=USER_ID, session_id=before.id, state=dict(before.state or {})
            )
            for event in before.events:
                await self.session_service.append_event(restored, event)
        except Exception as exc:  # noqa: BLE001
            logger.error("Session rollback failed (%s)", type(exc).__name__)

    async def reset(self, conversation_id: str) -> None:
        try:
            await self.session_service.delete_session(app_name=APP_NAME, user_id=USER_ID,
                                                      session_id=conversation_id)
        except Exception:  # noqa: BLE001 - unknown id: nothing to forget
            pass

    # -- one turn ----------------------------------------------------------------
    async def run_turn(self, conversation_id: str, text: str) -> str:
        lock = self._locks.setdefault(conversation_id, asyncio.Lock())
        async with lock:
            session = await self._get_or_create_session(conversation_id)
            before = copy.deepcopy(session)
            final_text = ""
            try:
                message = types.Content(role="user", parts=[types.Part(text=text)])
                async for event in self.runner.run_async(user_id=USER_ID, session_id=conversation_id,
                                                         new_message=message, run_config=STREAMING):
                    if event.author == self.root_agent.name and event.content and event.content.parts:
                        texts = [p.text for p in event.content.parts if p.text and not p.thought]
                        sink = tracing.current_sink()
                        if texts and event.partial and sink is not None:
                            sink.emit({"type": "answer_delta", "text": "".join(texts)})
                        elif texts and event.is_final_response():
                            final_text = "\n".join(texts)
                    if event.error_message and not final_text:
                        logger.warning("Model error event: %s", event.error_code or "error")
            except BaseException:
                await self._rollback(before)
                raise
            return final_text

    async def ask_stream(self, conversation_id: str, text: str, *,
                         keepalive_seconds: float = KEEPALIVE_SECONDS) -> AsyncIterator[dict[str, Any]]:
        started = time.perf_counter()
        yield {"type": "start", "conversation_id": conversation_id, "ts": tracing.now_ms()}

        if self.require_key and not self.settings.llm_key_configured:
            yield {"type": "error", "message": MISSING_KEY_MESSAGE, "ts": tracing.now_ms()}
            return

        queue: asyncio.Queue = asyncio.Queue()
        sink = tracing.TraceSink(queue, root_agent="main_agent")
        ctx = contextvars.copy_context()
        ctx.run(tracing.set_sink, sink)
        try:
            task = asyncio.create_task(self.run_turn(conversation_id, text), context=ctx)
        except Exception as exc:  # noqa: BLE001 - e.g. agent construction failed
            yield {"type": "error", "message": self._safe_error(exc), "ts": sink.ts()}
            return
        # Never cancel the turn if the client goes away: the answer is dropped but
        # the session stays consistent. Mark the exception retrieved.
        task.add_done_callback(lambda t: t.cancelled() or t.exception())

        while not task.done():
            getter = asyncio.ensure_future(queue.get())
            done, _ = await asyncio.wait({getter, task}, timeout=keepalive_seconds,
                                         return_when=asyncio.FIRST_COMPLETED)
            if getter in done:
                yield getter.result()
                continue
            getter.cancel()
            if task not in done:
                yield {"type": "ping"}
        while not queue.empty():
            yield queue.get_nowait()

        elapsed = int((time.perf_counter() - started) * 1000)
        try:
            answer = task.result()
        except Exception as exc:  # noqa: BLE001
            logger.exception("Chat turn failed")
            yield {"type": "error", "message": self._safe_error(exc), "ts": sink.ts()}
            return
        yield {
            "type": "answer",
            "text": answer or "_(The agent did not produce an answer. Try rephrasing the question.)_",
            "route": list(sink.route),
            "elapsed_ms": elapsed,
            "ts": sink.ts(),
        }

    def _safe_error(self, exc: BaseException) -> str:
        name = type(exc).__name__
        detail = str(exc).strip().splitlines()[0] if str(exc).strip() else ""
        text = f"The assistant failed to answer ({name}{': ' + detail[:300] if detail else ''})."
        lowered = (name + detail).lower()
        if "auth" in lowered or "api key" in lowered or "api_key" in lowered or "401" in lowered:
            text += " Check the LLM key in .env."
        return self.settings.scrub(text)
