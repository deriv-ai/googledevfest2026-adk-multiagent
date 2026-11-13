"""Shared runtime services (DB, registry, executor, news toolset).

Everything is created lazily so importing the agent tree (e.g. by `adk web`)
never touches the network. Tests build their own ``Services`` with fakes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .config import Settings, get_settings
from .db import Database, get_database
from .tools.executor import ToolExecutor
from .tools.news_toolset import NewsToolset
from .tools.registry import RegistryCache, ToolRepository
from .tools.spec import ToolSpec


@dataclass
class Services:
    settings: Settings
    db_provider: Any = None          # () -> Database
    repo: Any = None                 # ToolRepository-like
    executor: Any = None             # ToolExecutor-like (run_tool(spec, args))
    news_toolset: Any = None         # BaseToolset
    caches: dict[str, RegistryCache] = field(default_factory=dict)

    def database(self) -> Database:
        return self.db_provider() if self.db_provider else get_database()

    def repository(self) -> ToolRepository:
        if self.repo is None:
            return ToolRepository(self.database())
        return self.repo

    def tool_executor(self) -> ToolExecutor:
        if self.executor is None:
            return ToolExecutor(self.database(), max_rows=self.settings.tool_max_rows)
        return self.executor

    def test_executor(self) -> ToolExecutor:
        """Executor for POST /api/tools/test (unsaved tools are not logged)."""
        if self.executor is None:
            return ToolExecutor(self.database(), max_rows=self.settings.tool_max_rows, log_runs=False)
        return self.executor

    async def run_tool(self, spec: ToolSpec, args: dict[str, Any]) -> dict[str, Any]:
        return await self.tool_executor().run_tool(spec, args)

    def news(self) -> NewsToolset:
        if self.news_toolset is None:
            self.news_toolset = NewsToolset(self.settings.news_mcp_url)
        return self.news_toolset

    def cache(self, agent: str) -> RegistryCache:
        if agent not in self.caches:
            self.caches[agent] = RegistryCache(self.repository, agent)
        return self.caches[agent]


_services: Services | None = None


def get_services() -> Services:
    global _services
    if _services is None:
        _services = Services(settings=get_settings())
    return _services


def set_services(services: Services | None) -> None:
    global _services
    _services = services
