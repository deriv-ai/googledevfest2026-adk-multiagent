import inspect

from devfest_agents.tools.factory import RegistryTool, build_function, build_tool, declaration_json
from devfest_agents.tools.registry import RegistryCache
from devfest_agents.tools.spec import ToolSpec
from devfest_agents.tools.toolset import SqlRegistryToolset

from .helpers import KPI_FACTUAL, MONTHLY_PNL, TOP_INSTRUMENTS, FakeExecutor, FakeRepo


async def _echo(spec, kwargs):
    return {"tool": spec.name, "kwargs": kwargs}


async def test_generated_signature_and_call():
    spec = ToolSpec.model_validate(TOP_INSTRUMENTS)
    fn = build_function(spec, _echo)
    assert fn.__name__ == "trading_top_instruments"
    assert "Ranks instruments" in fn.__doc__
    sig = inspect.signature(fn)
    assert list(sig.parameters) == ["start_date", "end_date", "metric", "limit"]
    assert sig.parameters["start_date"].default is inspect.Parameter.empty
    assert sig.parameters["metric"].default == "commission"
    assert all(p.kind is inspect.Parameter.KEYWORD_ONLY for p in sig.parameters.values())
    out = await fn(start_date="2026-07-01", end_date="2026-07-31")
    assert out == {"tool": "trading_top_instruments", "kwargs": {"start_date": "2026-07-01", "end_date": "2026-07-31"}}


def test_sql_declaration_is_typed():
    decl = declaration_json(ToolSpec.model_validate(TOP_INSTRUMENTS))
    assert decl["name"] == "trading_top_instruments"
    params = decl["parameters"]
    assert set(params["required"]) == {"start_date", "end_date"}
    props = params["properties"]
    assert props["start_date"]["type"] == "string" and "YYYY-MM-DD" in props["start_date"]["description"]
    assert "2026-07-01" in props["start_date"]["description"]
    assert props["metric"]["enum"] == ["volume", "commission", "client_pnl"]
    assert props["metric"]["default"] == "commission"
    assert props["limit"]["type"] == "integer"
    assert props["limit"]["minimum"] == 1 and props["limit"]["maximum"] == 50


def test_optional_without_default_is_nullable():
    decl = declaration_json(ToolSpec.model_validate(MONTHLY_PNL))
    entity = decl["parameters"]["properties"]["entity_id"]
    assert "entity_id" not in decl["parameters"].get("required", [])
    assert {"type": "null"} in entity.get("anyOf", [])


async def test_factual_tool_has_no_args():
    spec = ToolSpec.model_validate(KPI_FACTUAL)
    decl = declaration_json(spec)
    assert decl["name"] == "kpi_definitions"
    assert not decl["parameters"].get("properties")
    tool = build_tool(spec, FakeExecutor(delay=0).run_tool)
    assert isinstance(tool, RegistryTool) and tool.tool_type == "factual"
    assert await tool.func() == {"answer": KPI_FACTUAL["answer"], "source": KPI_FACTUAL["source"]}


async def test_toolset_rebuilds_only_on_version_change():
    repo = FakeRepo([TOP_INSTRUMENTS])
    toolset = SqlRegistryToolset("trading", RegistryCache(lambda: repo, "trading"), FakeExecutor(0).run_tool)

    first = await toolset.get_tools()
    assert [t.name for t in first] == ["trading_top_instruments"]
    second = await toolset.get_tools()
    assert second[0] is first[0]  # unchanged registry -> identical tool objects
    assert toolset.rebuilds == 1 and repo.load_calls == 1

    # A new tool saved in the UI shows up on the next get_tools() - no restart.
    new_tool = dict(TOP_INSTRUMENTS, name="trading_clients_by_risk", title="Clients by risk level",
                    params=[], sql="SELECT c.risk_level, count(*) FROM trading.clients c GROUP BY 1")
    await repo.create(ToolSpec.model_validate(new_tool))
    third = await toolset.get_tools()
    assert sorted(t.name for t in third) == ["trading_clients_by_risk", "trading_top_instruments"]
    assert toolset.rebuilds == 2

    await repo.set_enabled("trading_top_instruments", False)
    fourth = await toolset.get_tools()
    assert [t.name for t in fourth] == ["trading_clients_by_risk"]

    # finance tools never leak into the trading toolset
    await repo.create(ToolSpec.model_validate(KPI_FACTUAL))
    assert [t.name for t in await toolset.get_tools()] == ["trading_clients_by_risk"]


async def test_toolset_survives_registry_outage():
    repo = FakeRepo([TOP_INSTRUMENTS])
    toolset = SqlRegistryToolset("trading", RegistryCache(lambda: repo, "trading"), FakeExecutor(0).run_tool)
    assert len(await toolset.get_tools()) == 1

    async def boom(agent):
        raise ConnectionError("db down")

    repo.version = boom
    assert [t.name for t in await toolset.get_tools()] == ["trading_top_instruments"]
