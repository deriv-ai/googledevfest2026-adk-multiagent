"""Shared fakes and fixtures data: no network, no API key, no database."""

from __future__ import annotations

import asyncio
import datetime as dt
from collections.abc import Callable
from typing import Any

from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse
from google.adk.tools import FunctionTool
from google.adk.tools.base_toolset import BaseToolset
from google.genai import types

from devfest_agents.config import Settings
from devfest_agents.services import Services
from devfest_agents.tools.executor import QueryResult, validate_args
from devfest_agents.tools.registry import ToolExistsError, ToolNotFoundError
from devfest_agents.tools.spec import ToolSpec

TOP_INSTRUMENTS = {
    "name": "trading_top_instruments",
    "agent": "trading",
    "tool_type": "sql",
    "title": "Top instruments by commission, volume or client PnL",
    "description": "Ranks instruments for a date range.",
    "params": [
        {"name": "start_date", "type": "date", "required": True, "description": "Inclusive start",
         "example": "2026-07-01"},
        {"name": "end_date", "type": "date", "required": True, "description": "Inclusive end", "example": "2026-09-30"},
        {"name": "metric", "type": "string", "default": "commission", "enum": ["volume", "commission", "client_pnl"]},
        {"name": "limit", "type": "integer", "default": 10, "min": 1, "max": 50},
    ],
    "sql": (
        "SELECT i.symbol, i.name, SUM(t.commission_usd) AS commission_usd\n"
        "FROM trading.trades t JOIN trading.instruments i USING (symbol)\n"
        "WHERE t.close_time::date BETWEEN :start_date AND :end_date\n"
        "GROUP BY 1, 2\n"
        "ORDER BY CASE :metric WHEN 'volume' THEN SUM(t.notional_usd) ELSE SUM(t.commission_usd) END DESC\n"
        "LIMIT :limit"
    ),
}

MONTHLY_PNL = {
    "name": "finance_monthly_pnl",
    "agent": "finance",
    "tool_type": "sql",
    "title": "Monthly P&L",
    "description": "Revenue, expenses and operating profit per month.",
    "params": [
        {"name": "start_month", "type": "date", "required": True, "example": "2026-07-01"},
        {"name": "end_month", "type": "date", "required": True, "example": "2026-09-01"},
        {"name": "entity_id", "type": "string", "description": "Entity filter, e.g. NM-UK"},
    ],
    "sql": (
        "SELECT date_trunc('month', g.entry_date)::date AS month, SUM(g.amount_usd) AS amount_usd\n"
        "FROM finance.gl_entries g JOIN finance.accounts a USING (account_code)\n"
        "WHERE g.entry_date >= :start_month AND g.entry_date < (:end_month::date + interval '1 month')\n"
        "  AND (:entity_id IS NULL OR g.entity_id = :entity_id)\n"
        "GROUP BY 1 ORDER BY 1"
    ),
}

KPI_FACTUAL = {
    "name": "kpi_definitions",
    "agent": "finance",
    "tool_type": "factual",
    "title": "KPI definitions",
    "description": "How Nimbus defines net revenue and other KPIs.",
    "answer": "**Net revenue** = commission + spread revenue - rebates.",
    "source": "Nimbus Finance Handbook 2.1",
}


def make_settings() -> Settings:
    return Settings(_env_file=None, gemini_api_key="test-key-not-real", database_url="postgresql://x@nowhere/x",
                    agent_database_url="postgresql://x@nowhere/x", news_mcp_url="http://127.0.0.1:9/mcp",
                    static_dir="/nonexistent", starter_tools_path="/nonexistent.yaml")


class FakeRepo:
    def __init__(self, specs: list[dict] | None = None):
        self.rows: dict[str, dict] = {}
        self.clock = 0
        self.version_calls = 0
        self.load_calls = 0
        for s in specs or []:
            self._put(ToolSpec.model_validate(s))

    def _put(self, spec: ToolSpec) -> dict:
        self.clock += 1
        row = spec.to_api() | {"updated_at": f"t{self.clock}", "created_at": "t0", "last_run": None}
        self.rows[spec.name] = row
        return row

    async def version(self, agent):
        self.version_calls += 1
        rows = [r for r in self.rows.values() if r["agent"] == agent and r["enabled"]]
        return (len(rows), max((r["updated_at"] for r in rows), default=None))

    async def enabled_specs(self, agent):
        self.load_calls += 1
        return [ToolSpec.model_validate(r) for r in sorted(self.rows.values(), key=lambda r: r["name"])
                if r["agent"] == agent and r["enabled"]]

    async def list_tools(self, agent=None, q=None):
        return [dict(r) for r in self.rows.values() if (agent is None or r["agent"] == agent)
                and (not q or q in r["name"] or q in r["title"])]

    async def list_tools_by_name(self, name):
        return [dict(self.rows[name])] if name in self.rows else []

    async def get_tool(self, name):
        return dict(self.rows[name]) | {"runs": []} if name in self.rows else None

    async def create(self, spec):
        if spec.name in self.rows:
            raise ToolExistsError(spec.name)
        return dict(self._put(spec))

    async def update(self, name, spec):
        if name not in self.rows:
            raise ToolNotFoundError(name)
        return dict(self._put(spec))

    async def set_enabled(self, name, enabled):
        if name not in self.rows:
            raise ToolNotFoundError(name)
        self.clock += 1
        self.rows[name].update(enabled=enabled, updated_at=f"t{self.clock}")
        return dict(self.rows[name])

    async def delete(self, name):
        if self.rows.pop(name, None) is None:
            raise ToolNotFoundError(name)

    async def upsert_seed(self, spec, *, force=False):
        if spec.name in self.rows and not force:
            return "skipped"
        existed = spec.name in self.rows
        self._put(spec)
        return "updated" if existed else "inserted"


class FakeExecutor:
    def __init__(self, delay: float = 0.05):
        self.delay = delay
        self.calls: list[tuple[str, dict]] = []

    async def run_tool(self, spec, args):
        self.calls.append((spec.name, dict(args)))
        await asyncio.sleep(self.delay)
        if spec.tool_type == "factual":
            return {"answer": spec.answer, "source": spec.source}
        values = validate_args(spec.params, args)
        return {"tool": spec.name, "params": {k: str(v) for k, v in values.items()}, "row_count": 2,
                "truncated": False, "columns": ["k", "v"], "rows": [{"k": "a", "v": 1.0}, {"k": "b", "v": 2.0}],
                "summary": "2 rows"}

    async def run_query(self, spec, values):
        self.calls.append((spec.name, dict(values)))
        return QueryResult(columns=["symbol", "commission_usd"], rows=[["BTCUSD", 10.5]], truncated=False,
                           duration_ms=3)


async def search_news(query: str, limit: int = 5) -> dict:
    """Search recent news (fake)."""
    await asyncio.sleep(0.02)
    return {"result": [{"title": f"News about {query}", "source": "Fake Wire", "published": "2026-11-05"}]}


class FakeNewsToolset(BaseToolset):
    def __init__(self):
        super().__init__()
        self.last_tool_names = ["search_news"]
        self.available = True
        self._tools = [FunctionTool(search_news)]

    async def get_tools(self, readonly_context=None):
        return self._tools


class FakeDB:
    def __init__(self, ok: bool = True):
        self.ok = ok

    async def ping(self):
        return self.ok

    async def ensure_open(self):
        return None

    async def close(self):
        return None


def make_fake_services(settings) -> Services:
    return Services(settings=settings, db_provider=lambda: FakeDB(), repo=FakeRepo([TOP_INSTRUMENTS, MONTHLY_PNL]),
                    executor=FakeExecutor(), news_toolset=FakeNewsToolset())


# ---------------------------------------------------------------------------
# Scripted LLM
# ---------------------------------------------------------------------------
Responder = Callable[[Any, int], list[types.Part]]


class ScriptedLlm(BaseLlm):
    """Returns scripted parts. The responder gets (llm_request, function responses seen this turn)."""

    responder: Any
    delay: float = 0.02
    fail: bool = False
    fail_after: int | None = None  # fail once this many function responses were seen

    async def generate_content_async(self, llm_request, stream: bool = False):
        # Count function responses since the latest user text (i.e. in this turn).
        contents = list(llm_request.contents)
        start = 0
        for i, c in enumerate(contents):
            if c.role == "user" and any(p.text for p in (c.parts or [])):
                start = i
        seen = sum(1 for c in contents[start:] for p in (c.parts or []) if p.function_response)
        if self.fail or (self.fail_after is not None and seen >= self.fail_after):
            raise RuntimeError("scripted model failure")
        await asyncio.sleep(self.delay)
        parts = self.responder(llm_request, seen)
        yield LlmResponse(content=types.Content(role="model", parts=parts))


_call_counter = 0


def call(name: str, **args) -> types.Part:
    global _call_counter
    _call_counter += 1
    return types.Part(function_call=types.FunctionCall(name=name, args=args, id=f"fc-{_call_counter}"))


def text(t: str) -> types.Part:
    return types.Part(text=t)


def today_iso() -> str:
    return dt.date.today().isoformat()
