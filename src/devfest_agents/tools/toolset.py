"""Hot-reloaded registry tools for one agent.

ADK calls ``BaseToolset.get_tools()`` before every model call. Each call does
one cheap version query; the FunctionTool list is rebuilt only when that
version changes. A tool saved (or toggled) in the UI is therefore callable on
the very next question, with no restart, and an unchanged registry returns the
identical tool objects.
"""

from __future__ import annotations

import logging
from typing import Optional

from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.tools.base_tool import BaseTool
from google.adk.tools.base_toolset import BaseToolset

from .factory import ToolRunner, build_tool
from .registry import RegistryCache

logger = logging.getLogger(__name__)


class SqlRegistryToolset(BaseToolset):
    def __init__(self, agent: str, cache: RegistryCache, runner: ToolRunner):
        super().__init__()
        self.agent = agent
        self._cache = cache
        self._runner = runner
        self._built_version: tuple | None = None
        self._tools: list[BaseTool] = []
        self.rebuilds = 0

    async def get_tools(self, readonly_context: Optional[ReadonlyContext] = None) -> list[BaseTool]:
        specs, _ = await self._cache.refresh()
        version = self._cache.version
        if version != self._built_version or (not self._tools and specs):
            tools: list[BaseTool] = []
            for spec in specs:
                try:
                    tools.append(build_tool(spec, self._runner))
                except Exception as exc:  # noqa: BLE001 - one bad row must not hide the rest
                    logger.warning("Could not build tool %s: %s", spec.name, exc)
            self._tools = tools
            self._built_version = version
            self.rebuilds += 1
            logger.info("%s toolset rebuilt: %s", self.agent, [t.name for t in tools] or "(no tools)")
        return [t for t in self._tools if self._is_tool_selected(t, readonly_context)]

    async def close(self) -> None:
        # AgentTool closes the wrapped agent's toolsets after every call; the
        # cached tools are stateless, so there is nothing to release.
        return None
