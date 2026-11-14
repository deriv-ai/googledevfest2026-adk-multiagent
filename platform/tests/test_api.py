"""API routes with the database and LLM faked."""

import json

import pytest
from fastapi.testclient import TestClient

from devfest_agents.api.main import create_app
from devfest_agents.api.routes_chat import sse_frame
from devfest_agents.runtime import AgentRuntime

from .helpers import KPI_FACTUAL, TOP_INSTRUMENTS
from .test_tracing import build_tree


class FakeSchema:
    async def list_schemas(self):
        return {"schemas": [{"name": "finance", "comment": "GL"}]}

    async def describe(self, schema):
        return {"name": schema, "comment": "c", "tables": [{"name": "entities", "comment": "x", "row_count": 4,
                                                            "columns": []}]}

    async def sample(self, schema, table, limit=5):
        from devfest_agents.schema_introspect import UnknownSchemaObject

        if table != "entities":
            raise UnknownSchemaObject(table)
        return {"columns": ["entity_id"], "rows": [["NM-UK"]][:limit]}


@pytest.fixture
def client(fake_services):
    runtime = AgentRuntime(agent_factory=lambda: build_tree(fake_services), settings=fake_services.settings)
    app = create_app(services=fake_services, runtime=runtime, schema=FakeSchema(), connect_db=False)
    with TestClient(app) as c:
        yield c


def test_health(client):
    body = client.get("/api/health").json()
    assert body == {"ok": True, "db": "ok", "llm_key": "configured", "llm_mode": "direct",
                    "model": "gemini/gemini-3.5-flash-lite", "router_model": "gemini/gemini-3.5-flash-lite"}
    assert "test-key-not-real" not in json.dumps(body)


def test_graph(client):
    body = client.get("/api/graph").json()
    ids = [a["id"] for a in body["agents"]]
    assert ids == ["main_agent", "orchestrator", "finance_agent", "trading_agent", "news_agent", "marketing_agent"]
    assert body["agents"][2]["datasource"] == "finance" and body["agents"][1]["parent"] == "main_agent"
    tools = {t["name"]: t for t in body["tools"]}
    assert tools["trading_top_instruments"]["agent"] == "trading_agent"
    assert tools["channel_summary"] == {"name": "channel_summary", "agent": "marketing_agent", "tool_type": "function",
                                        "title": "Spend per ad channel for a date range."}
    assert tools["search_news"]["agent"] == "news_agent"
    assert body["datasources"] == [{"id": "finance", "label": "finance schema"},
                                   {"id": "trading", "label": "trading schema"},
                                   {"id": "internet", "label": "Internet (RSS)"},
                                   {"id": "marketing", "label": "marketing schema"}]


def test_examples(client):
    examples = client.get("/api/chat/examples").json()
    assert len(examples) >= 8 and all({"label", "prompt"} <= set(e) for e in examples)


def test_chat_sse(client):
    with client.stream("POST", "/api/chat", json={"conversation_id": "abc-1", "message": "hello"}) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        assert resp.headers["cache-control"] == "no-cache"
        assert resp.headers["x-accel-buffering"] == "no"
        raw = "".join(resp.iter_text())
    frames = [f for f in raw.split("\n\n") if f]
    assert all(f.startswith("data: ") or f == ": ping" for f in frames)
    events = [json.loads(f[6:]) for f in frames if f.startswith("data: ")]
    assert events[0] == {"type": "start", "conversation_id": "abc-1", "ts": events[0]["ts"]}
    assert events[-1]["type"] == "answer"
    assert any(e["type"] == "tool_call" and e["kind"] == "agent" for e in events)
    assert client.post("/api/chat/reset", json={"conversation_id": "abc-1"}).json() == {"ok": True}


def test_chat_validation(client):
    assert client.post("/api/chat", json={"conversation_id": "bad id!", "message": "x"}).status_code == 422
    assert client.post("/api/chat", json={"conversation_id": "ok", "message": "  "}).status_code == 422
    r = client.post("/api/chat", json={"message": "x"})
    assert r.status_code == 422 and "detail" in r.json()


def test_sse_frame():
    assert sse_frame({"type": "ping"}) == ": ping\n\n"
    assert sse_frame({"type": "answer", "text": "é"}) == 'data: {"type": "answer", "text": "é"}\n\n'


def test_tools_crud(client):
    tools = client.get("/api/tools").json()
    assert {t["name"] for t in tools} == {"trading_top_instruments", "finance_monthly_pnl"}
    assert client.get("/api/tools", params={"agent": "finance"}).json()[0]["name"] == "finance_monthly_pnl"

    r = client.post("/api/tools", json=KPI_FACTUAL)
    assert r.status_code == 201 and r.json()["answer"].startswith("**Net revenue**")
    assert client.post("/api/tools", json=KPI_FACTUAL).status_code == 409

    bad = client.post("/api/tools", json=dict(TOP_INSTRUMENTS, name="trading_bad", sql="DELETE FROM trading.trades"))
    assert bad.status_code == 422 and bad.json()["errors"]

    one = client.get("/api/tools/kpi_definitions").json()
    assert one["runs"] == []
    assert client.get("/api/tools/nope").status_code == 404

    updated = client.put("/api/tools/kpi_definitions", json=dict(KPI_FACTUAL, title="KPI glossary"))
    assert updated.status_code == 200 and updated.json()["title"] == "KPI glossary"
    assert client.put("/api/tools/kpi_definitions", json=dict(KPI_FACTUAL, name="renamed")).status_code == 422

    assert client.patch("/api/tools/kpi_definitions/enabled", json={"enabled": False}).json()["enabled"] is False
    assert client.patch("/api/tools/kpi_definitions/enabled", json={"enabled": "no"}).status_code == 422
    assert client.delete("/api/tools/kpi_definitions").json() == {"ok": True}
    assert client.delete("/api/tools/kpi_definitions").status_code == 404


def test_tool_test_sql(client, fake_services):
    body = client.post("/api/tools/test", json=TOP_INSTRUMENTS).json()
    assert body["ok"] is True and body["errors"] == []
    assert body["declaration"]["name"] == "trading_top_instruments"
    assert "start_date" in body["declaration"]["parameters"]["properties"]
    assert body["result"] == {"columns": ["symbol", "commission_usd"], "rows": [["BTCUSD", 10.5]], "row_count": 1,
                              "truncated": False, "duration_ms": 3}
    name, values = fake_services.executor.calls[-1]
    assert str(values["start_date"]) == "2026-07-01" and values["limit"] == 10  # example + default

    with_args = client.post("/api/tools/test", json=dict(TOP_INSTRUMENTS, args={"limit": 99})).json()
    assert with_args["ok"] is False and "<= 50" in with_args["errors"][0] and with_args["declaration"]


def test_tool_test_failures_are_http_200(client):
    lint = client.post("/api/tools/test", json=dict(TOP_INSTRUMENTS, sql="SELECT * FROM finance.gl_entries"))
    assert lint.status_code == 200
    body = lint.json()
    assert body["ok"] is False and body["result"] is None and body["errors"]

    no_example = dict(TOP_INSTRUMENTS, params=[dict(p, example=None) if p["name"] == "start_date" else p
                                               for p in TOP_INSTRUMENTS["params"]])
    body = client.post("/api/tools/test", json=no_example).json()
    assert body["ok"] is False and "start_date" in body["errors"][0]


def test_tool_test_factual(client):
    body = client.post("/api/tools/test", json=KPI_FACTUAL).json()
    assert body["ok"] is True
    assert body["result"] == {"answer": KPI_FACTUAL["answer"], "source": KPI_FACTUAL["source"]}
    assert body["declaration"]["name"] == "kpi_definitions"


def test_schema_routes(client):
    assert client.get("/api/schema").json()["schemas"][0]["name"] == "finance"
    assert client.get("/api/schema/finance").json()["tables"][0]["row_count"] == 4
    assert client.get("/api/schema/public").status_code == 404
    assert client.get("/api/schema/finance/entities/sample", params={"limit": 1}).json()["rows"] == [["NM-UK"]]
    assert client.get("/api/schema/finance/entities/sample", params={"limit": 51}).status_code == 422
    assert client.get("/api/schema/finance/nope/sample").status_code == 404


def test_missing_key_chat(fake_services, monkeypatch):
    from devfest_agents.config import Settings

    fake_services.settings = Settings(_env_file=None)
    app = create_app(services=fake_services, schema=FakeSchema(), connect_db=False)
    with TestClient(app) as c:
        raw = c.post("/api/chat", json={"conversation_id": "x", "message": "hi"}).text
        assert "LLM_API_KEY" in raw and '"type": "error"' in raw
        assert c.get("/api/tools").status_code == 200  # app works without a key


def test_spa_fallback(fake_services, tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("console.log(1)")
    (tmp_path / "index.html").write_text("<html>spa</html>")
    fake_services.settings.static_dir = str(tmp_path)
    app = create_app(services=fake_services, schema=FakeSchema(), connect_db=False)
    with TestClient(app) as c:
        assert c.get("/tools/new").text == "<html>spa</html>"
        assert c.get("/assets/app.js").text == "console.log(1)"
        assert c.get("/api/does-not-exist").status_code == 404
        assert c.get("/api/does-not-exist").json() == {"detail": "Not found"}
