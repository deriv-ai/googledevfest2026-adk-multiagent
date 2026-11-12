"""The tool registry: rows in ``tools.tools``.

``ToolRepository`` is the only code that reads/writes the table (API, seeder,
toolsets). ``RegistryCache`` keeps the enabled specs for one agent and reloads
them only when a cheap version query (``count(*), max(updated_at)``) changes.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from .executor import json_safe
from .spec import ToolSpec

if TYPE_CHECKING:
    from ..db import Database

logger = logging.getLogger(__name__)

_COLUMNS = ("name, agent, tool_type, title, description, sql_text, params, answer_text, source, enabled, "
            "created_at, updated_at")


class ToolExistsError(Exception):
    pass


class ToolNotFoundError(Exception):
    pass


def row_to_spec(row: dict[str, Any]) -> ToolSpec:
    return ToolSpec.model_validate(
        {
            "name": row["name"],
            "agent": row["agent"],
            "tool_type": row["tool_type"],
            "title": row["title"],
            "description": row["description"],
            "params": row.get("params") or [],
            "sql": row.get("sql_text"),
            "answer": row.get("answer_text"),
            "source": row.get("source"),
            "enabled": row.get("enabled", True),
        }
    )


def row_to_api(row: dict[str, Any]) -> dict[str, Any]:
    """DB row -> API tool object (contract keys)."""
    out = {
        "name": row["name"],
        "agent": row["agent"],
        "tool_type": row["tool_type"],
        "title": row["title"],
        "description": row["description"],
        "enabled": row["enabled"],
        "params": row.get("params") or [],
        "sql": row.get("sql_text"),
        "answer": row.get("answer_text"),
        "source": row.get("source"),
        "created_at": json_safe(row.get("created_at")),
        "updated_at": json_safe(row.get("updated_at")),
        "last_run": None,
    }
    if row.get("last_run_at") is not None:
        out["last_run"] = {
            "created_at": json_safe(row["last_run_at"]),
            "row_count": row.get("last_run_row_count"),
            "duration_ms": row.get("last_run_duration_ms"),
            "error": row.get("last_run_error"),
        }
    return out


def _spec_values(spec: ToolSpec) -> dict[str, Any]:
    return {
        "name": spec.name,
        "agent": spec.agent,
        "tool_type": spec.tool_type,
        "title": spec.title,
        "description": spec.description,
        "sql_text": spec.sql,
        "params": Jsonb([p.as_dict() for p in spec.params]),
        "answer_text": spec.answer,
        "source": spec.source,
        "enabled": spec.enabled,
    }


class ToolRepository:
    def __init__(self, db: "Database"):
        self.db = db

    async def _fetch(self, query: str, params: Any = None) -> list[dict[str, Any]]:
        await self.db.ensure_open()
        async with self.db.app_pool.connection(timeout=10.0) as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute(query, params)
                return list(await cur.fetchall()) if cur.description else []

    # ---- reads -------------------------------------------------------------
    async def list_tools(self, agent: str | None = None, q: str | None = None) -> list[dict[str, Any]]:
        where, params = [], {}
        if agent:
            where.append("t.agent = %(agent)s")
            params["agent"] = agent
        if q:
            where.append("(t.name ILIKE %(q)s OR t.title ILIKE %(q)s OR t.description ILIKE %(q)s)")
            params["q"] = f"%{q}%"
        sql = (
            f"SELECT {', '.join('t.' + c.strip() for c in _COLUMNS.split(','))}, "
            "r.created_at AS last_run_at, r.row_count AS last_run_row_count, "
            "r.duration_ms AS last_run_duration_ms, r.error AS last_run_error "
            "FROM tools.tools t "
            "LEFT JOIN LATERAL (SELECT created_at, row_count, duration_ms, error FROM tools.tool_runs "
            "  WHERE name = t.name ORDER BY created_at DESC LIMIT 1) r ON true "
            + (f"WHERE {' AND '.join(where)} " if where else "")
            + "ORDER BY t.agent, t.tool_type, t.name"
        )
        return [row_to_api(r) for r in await self._fetch(sql, params)]

    async def get_tool(self, name: str) -> dict[str, Any] | None:
        rows = await self.list_tools_by_name(name)
        if not rows:
            return None
        tool = rows[0]
        tool["runs"] = await self.recent_runs(name)
        return tool

    async def list_tools_by_name(self, name: str) -> list[dict[str, Any]]:
        sql = (
            f"SELECT {', '.join('t.' + c.strip() for c in _COLUMNS.split(','))}, "
            "r.created_at AS last_run_at, r.row_count AS last_run_row_count, "
            "r.duration_ms AS last_run_duration_ms, r.error AS last_run_error "
            "FROM tools.tools t "
            "LEFT JOIN LATERAL (SELECT created_at, row_count, duration_ms, error FROM tools.tool_runs "
            "  WHERE name = t.name ORDER BY created_at DESC LIMIT 1) r ON true "
            "WHERE t.name = %(name)s"
        )
        return [row_to_api(r) for r in await self._fetch(sql, {"name": name})]

    async def recent_runs(self, name: str, limit: int = 10) -> list[dict[str, Any]]:
        rows = await self._fetch(
            "SELECT id, name, agent, args, row_count, duration_ms, error, created_at FROM tools.tool_runs "
            "WHERE name = %s ORDER BY created_at DESC, id DESC LIMIT %s",
            (name, limit),
        )
        return [json_safe(r) for r in rows]

    async def exists(self, name: str) -> bool:
        return bool(await self._fetch("SELECT 1 FROM tools.tools WHERE name = %s", (name,)))

    async def enabled_specs(self, agent: str) -> list[ToolSpec]:
        rows = await self._fetch(
            f"SELECT {_COLUMNS} FROM tools.tools WHERE agent = %s AND enabled ORDER BY name", (agent,)
        )
        specs = []
        for row in rows:
            try:
                specs.append(row_to_spec(row))
            except Exception as exc:  # noqa: BLE001 - a bad row must not take the agent down
                logger.warning("Skipping invalid tool row %s: %s", row.get("name"), exc)
        return specs

    async def version(self, agent: str) -> tuple[int, Any]:
        rows = await self._fetch(
            "SELECT count(*) AS n, max(updated_at) AS v FROM tools.tools WHERE agent = %s AND enabled", (agent,)
        )
        return (rows[0]["n"], rows[0]["v"]) if rows else (0, None)

    # ---- writes ------------------------------------------------------------
    async def create(self, spec: ToolSpec) -> dict[str, Any]:
        vals = _spec_values(spec)
        rows = await self._fetch(
            "INSERT INTO tools.tools (name, agent, tool_type, title, description, sql_text, params, answer_text, "
            "source, enabled) VALUES (%(name)s, %(agent)s, %(tool_type)s, %(title)s, %(description)s, %(sql_text)s, "
            "%(params)s, %(answer_text)s, %(source)s, %(enabled)s) ON CONFLICT (name) DO NOTHING RETURNING name",
            vals,
        )
        if not rows:
            raise ToolExistsError(spec.name)
        return (await self.list_tools_by_name(spec.name))[0]

    async def update(self, name: str, spec: ToolSpec) -> dict[str, Any]:
        vals = _spec_values(spec)
        vals["name"] = name
        rows = await self._fetch(
            "UPDATE tools.tools SET agent=%(agent)s, tool_type=%(tool_type)s, title=%(title)s, "
            "description=%(description)s, sql_text=%(sql_text)s, params=%(params)s, answer_text=%(answer_text)s, "
            "source=%(source)s, enabled=%(enabled)s, updated_at=now() WHERE name=%(name)s RETURNING name",
            vals,
        )
        if not rows:
            raise ToolNotFoundError(name)
        return (await self.list_tools_by_name(name))[0]

    async def set_enabled(self, name: str, enabled: bool) -> dict[str, Any]:
        rows = await self._fetch(
            "UPDATE tools.tools SET enabled=%s, updated_at=now() WHERE name=%s RETURNING name", (enabled, name)
        )
        if not rows:
            raise ToolNotFoundError(name)
        return (await self.list_tools_by_name(name))[0]

    async def delete(self, name: str) -> None:
        rows = await self._fetch("DELETE FROM tools.tools WHERE name=%s RETURNING name", (name,))
        if not rows:
            raise ToolNotFoundError(name)

    async def upsert_seed(self, spec: ToolSpec, *, force: bool = False) -> str:
        """Insert a starter tool. Returns 'inserted', 'updated' or 'skipped'."""
        vals = _spec_values(spec)
        if force:
            rows = await self._fetch(
                "INSERT INTO tools.tools (name, agent, tool_type, title, description, sql_text, params, "
                "answer_text, source, enabled) VALUES (%(name)s, %(agent)s, %(tool_type)s, %(title)s, "
                "%(description)s, %(sql_text)s, %(params)s, %(answer_text)s, %(source)s, %(enabled)s) "
                "ON CONFLICT (name) DO UPDATE SET agent=EXCLUDED.agent, tool_type=EXCLUDED.tool_type, "
                "title=EXCLUDED.title, description=EXCLUDED.description, sql_text=EXCLUDED.sql_text, "
                "params=EXCLUDED.params, answer_text=EXCLUDED.answer_text, source=EXCLUDED.source, "
                "enabled=EXCLUDED.enabled, updated_at=now() RETURNING (xmax = 0) AS inserted",
                vals,
            )
            return "inserted" if rows and rows[0]["inserted"] else "updated"
        rows = await self._fetch(
            "INSERT INTO tools.tools (name, agent, tool_type, title, description, sql_text, params, answer_text, "
            "source, enabled) VALUES (%(name)s, %(agent)s, %(tool_type)s, %(title)s, %(description)s, %(sql_text)s, "
            "%(params)s, %(answer_text)s, %(source)s, %(enabled)s) ON CONFLICT (name) DO NOTHING RETURNING name",
            vals,
        )
        return "inserted" if rows else "skipped"


class RegistryCache:
    """Enabled specs for one agent, refreshed only when the version changes."""

    def __init__(self, repo_provider, agent: str):
        self._repo_provider = repo_provider
        self.agent = agent
        self._version: tuple | None = None
        self._specs: list[ToolSpec] = []
        self._lock = asyncio.Lock()
        self.reloads = 0

    @property
    def specs(self) -> list[ToolSpec]:
        return list(self._specs)

    @property
    def version(self) -> tuple | None:
        return self._version

    async def refresh(self) -> tuple[list[ToolSpec], bool]:
        """Return (specs, changed). On DB errors keep serving the last good list."""
        repo = self._repo_provider()
        async with self._lock:
            try:
                version = await repo.version(self.agent)
                if version == self._version:
                    return list(self._specs), False
                specs = await repo.enabled_specs(self.agent)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Tool registry unavailable for %s (%s); using last known tools",
                               self.agent, type(exc).__name__)
                return list(self._specs), False
            self._specs = specs
            self._version = version
            self.reloads += 1
            logger.info("Loaded %d enabled %s tool(s)", len(specs), self.agent)
            return list(specs), True
