"""Fail-soft wrapper around ADK's McpToolset for the news-mcp server.

If the MCP server is down, the news agent simply has no tools for that turn
(and says so) instead of the whole question failing. A failed connection is
remembered for a short back-off so every turn doesn't wait on a timeout.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Optional

from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.base_toolset import BaseToolset

logger = logging.getLogger(__name__)

# ADK's MCP client otherwise probes Google Application Default Credentials for
# mTLS before connecting (several seconds, and pointless for a local server).
os.environ.setdefault("GOOGLE_API_USE_CLIENT_CERTIFICATE", "false")

class NewsToolset(BaseToolset):
    def __init__(self, url: str, *, connect_timeout: float = 5.0, retry_after_s: float = 30.0,
                 list_timeout_s: float = 15.0):
        super().__init__()
        self.url = url
        self._connect_timeout = connect_timeout
        self._retry_after_s = retry_after_s
        self._list_timeout_s = list_timeout_s
        self._inner = None
        self._down_until = 0.0
        self.last_error: str | None = None

    def _make_inner(self):
        from google.adk.tools.mcp_tool import McpToolset, StreamableHTTPConnectionParams

        return McpToolset(
            connection_params=StreamableHTTPConnectionParams(url=self.url, timeout=self._connect_timeout),
            tool_list_cache_ttl_seconds=60,
        )

    @property
    def available(self) -> bool:
        return time.monotonic() >= self._down_until

    async def get_tools(self, readonly_context: Optional[ReadonlyContext] = None) -> list[BaseTool]:
        if not self.available:
            return []
        try:
            if self._inner is None:
                self._inner = self._make_inner()
            tools = await asyncio.wait_for(self._inner.get_tools(readonly_context), timeout=self._list_timeout_s)
        except BaseException as exc:  # noqa: BLE001 - includes anyio/ExceptionGroup from the MCP client
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            if isinstance(exc, asyncio.CancelledError) and not isinstance(exc, asyncio.TimeoutError):
                current = asyncio.current_task()
                if current is not None and current.cancelling():
                    raise
            self.last_error = type(exc).__name__
            self._down_until = time.monotonic() + self._retry_after_s
            logger.warning("news-mcp unreachable (%s); news tools disabled for %.0fs", self.last_error,
                           self._retry_after_s)
            await self._reset_inner()
            return []
        self.last_error = None
        return [t for t in tools if self._is_tool_selected(t, readonly_context)]

    async def _reset_inner(self) -> None:
        inner, self._inner = self._inner, None
        if inner is not None:
            try:
                await inner.close()
            except BaseException:  # noqa: BLE001
                pass

    async def close(self) -> None:
        # AgentTool calls close() on the wrapped agent's toolsets after EVERY
        # news_agent run, and parallel runs share this toolset, so closing the
        # MCP session here would break a concurrent call. Keep it; shutdown()
        # releases it when the app stops.
        return None

    async def shutdown(self) -> None:
        await self._reset_inner()
