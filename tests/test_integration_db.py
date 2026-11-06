"""Integration tests against the compose Postgres on localhost:5432.

    make up   (or start just the db service), then:
    .venv/bin/pytest -m integration

Override the URLs with IT_DATABASE_URL / IT_AGENT_DATABASE_URL if needed.
"""

import os

import pytest

from devfest_agents.config import REPO_ROOT, Settings
from devfest_agents.db import Database
from devfest_agents.schema_introspect import SchemaService
from devfest_agents.seed import load_starter_specs, seed_tools
from devfest_agents.services import Services
from devfest_agents.tools.executor import ToolExecutor
from devfest_agents.tools.registry import RegistryCache, ToolRepository
from devfest_agents.tools.spec import ToolSpec
from devfest_agents.tools.toolset import SqlRegistryToolset

pytestmark = pytest.mark.integration

APP_URL = os.environ.get("IT_DATABASE_URL", "postgresql://app:app@localhost:5432/nimbus")
AGENT_URL = os.environ.get("IT_AGENT_DATABASE_URL", "postgresql://agent_ro:agent_ro@localhost:5432/nimbus")
STARTER = REPO_ROOT / "seed" / "starter_tools.yaml"


@pytest.fixture
async def db():
    database = Database(APP_URL, AGENT_URL, max_size=4)
    if not await database.open(attempts=1, timeout=3.0):
        await database.close()
        pytest.skip("Postgres on localhost:5432 is not reachable")
    yield database
    await database.close()


async def test_seed_is_idempotent(db):
    repo = ToolRepository(db)
    first = await seed_tools(repo, STARTER)
    assert first["errors"] == []
    second = await seed_tools(repo, STARTER)
    assert second["inserted"] == [] and len(second["skipped"]) == 6


async def test_every_starter_tool_returns_rows(db):
    specs, errors = load_starter_specs(STARTER)
    assert errors == [] and len(specs) == 6
    executor = ToolExecutor(db, max_rows=200, log_runs=True)
    for spec in specs:
        args = {p.name: p.example for p in spec.params if p.example is not None}
        out = await executor.run_tool(spec, args)
        assert "error" not in out, (spec.name, out)
        assert out["row_count"] > 0, (spec.name, out)
        assert isinstance(out["rows"][0], dict)


async def test_tool_errors_are_model_readable(db):
    spec = ToolSpec.model_validate({
        "name": "trading_bad_column", "agent": "trading", "tool_type": "sql", "title": "t", "description": "d",
        "sql": "SELECT no_such_column FROM trading.trades",
    })
    out = await ToolExecutor(db, log_runs=False).run_tool(spec, {})
    assert out["error"].startswith("trading_bad_column failed: Database error:")
    assert "no_such_column" in out["error"]


async def test_agent_role_cannot_touch_tools_or_write(db):
    executor = ToolExecutor(db, log_runs=False)
    # The guard would reject these; bypass it to prove the DB itself enforces it.
    for sql in ("SELECT * FROM tools.tools", "SELECT * FROM trading.clients FOR UPDATE"):
        spec = ToolSpec.model_construct(name="x_probe", agent="trading", tool_type="sql", title="t",
                                        description="d", params=[], sql=sql)
        out = await executor.run_tool(spec, {})
        assert "error" in out, sql


async def test_truncation_flag(db):
    spec = ToolSpec.model_validate({"name": "trading_all_trades", "agent": "trading", "tool_type": "sql",
                                    "title": "t", "description": "d",
                                    "sql": "SELECT t.trade_id FROM trading.trades t"})
    out = await ToolExecutor(db, max_rows=5, log_runs=False).run_tool(spec, {})
    assert out["row_count"] == 5 and out["truncated"] is True


async def test_hot_reload_against_real_registry(db):
    repo = ToolRepository(db)
    await seed_tools(repo, STARTER)
    toolset = SqlRegistryToolset("finance", RegistryCache(lambda: repo, "finance"),
                                 ToolExecutor(db, log_runs=False).run_tool)
    before = {t.name for t in await toolset.get_tools()}
    assert "finance_monthly_pnl" in before
    spec = ToolSpec.model_validate({"name": "finance_it_temp_tool", "agent": "finance", "tool_type": "factual",
                                    "title": "Temp", "description": "Temporary integration-test tool",
                                    "answer": "42", "source": "test"})
    try:
        await repo.create(spec)
        assert "finance_it_temp_tool" in {t.name for t in await toolset.get_tools()}
        await repo.set_enabled("finance_it_temp_tool", False)
        assert "finance_it_temp_tool" not in {t.name for t in await toolset.get_tools()}
    finally:
        await repo.delete("finance_it_temp_tool")
    assert {t.name for t in await toolset.get_tools()} == before


async def test_schema_introspection(db):
    svc = SchemaService(lambda: db)
    names = [s["name"] for s in (await svc.list_schemas())["schemas"]]
    assert names == ["finance", "trading", "tools"]
    finance = await svc.describe("finance")
    tables = {t["name"]: t for t in finance["tables"]}
    assert {"entities", "accounts", "gl_entries", "budgets", "fx_rates"} <= set(tables)
    gl = {c["name"]: c for c in tables["gl_entries"]["columns"]}
    assert gl["entry_id"]["pk"] is True
    assert gl["entity_id"]["fk"]["table"] == "entities" and gl["entity_id"]["fk"]["column"] == "entity_id"
    assert tables["gl_entries"]["row_count"] > 0 and tables["gl_entries"]["comment"]
    sample = await svc.sample("trading", "instruments", 3)
    assert len(sample["rows"]) == 3 and "symbol" in sample["columns"]


def test_api_against_real_db(monkeypatch):
    from fastapi.testclient import TestClient

    from devfest_agents.api.main import create_app

    settings = Settings(_env_file=None, database_url=APP_URL, agent_database_url=AGENT_URL,
                        starter_tools_path=str(STARTER), news_mcp_url="http://127.0.0.1:9/mcp")
    holder = {}

    def db_provider():
        if "db" not in holder:
            holder["db"] = Database(APP_URL, AGENT_URL, max_size=4)
        return holder["db"]

    app = create_app(services=Services(settings=settings, db_provider=db_provider), connect_db=True)
    with TestClient(app) as client:
        if client.get("/api/health").json()["db"] != "ok":
            pytest.skip("Postgres on localhost:5432 is not reachable")
        tools = client.get("/api/tools").json()
        assert len([t for t in tools if t["name"].startswith(("finance_", "trading_"))]) >= 6
        top = next(t for t in tools if t["name"] == "trading_top_instruments")
        body = client.post("/api/tools/test", json=top).json()
        assert body["ok"] is True, body["errors"]
        assert body["result"]["row_count"] > 0 and isinstance(body["result"]["rows"][0], list)
        detail = client.get("/api/schema/trading").json()
        assert any(t["name"] == "trades" for t in detail["tables"])
        graph = client.get("/api/graph").json()
        assert any(t["name"] == "finance_budget_vs_actual" for t in graph["tools"])
