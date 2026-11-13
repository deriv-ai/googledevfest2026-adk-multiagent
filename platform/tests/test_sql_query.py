"""run_sql(): the read-only SQL helper for hand-written Python tools."""

from devfest_agents.tools.sql_guard import compile_untyped_sql
from devfest_agents.tools.sql_query import run_sql


def test_compile_untyped_sql_keeps_casts_and_escapes_percent():
    sql = "SELECT * FROM marketing.campaigns c WHERE c.name LIKE 'Go%' AND (:entity_id::text IS NULL OR c.entity_id = :entity_id)"
    assert compile_untyped_sql(sql) == (
        "SELECT * FROM marketing.campaigns c WHERE c.name LIKE 'Go%%' "
        "AND (%(entity_id)s::text IS NULL OR c.entity_id = %(entity_id)s)"
    )


async def test_run_sql_returns_rows(fake_services):
    result = await run_sql("marketing", "SELECT c.channel FROM marketing.campaigns c WHERE c.start_date >= :start",
                           start="2026-07-01")
    assert result == {"row_count": 1, "truncated": False, "rows": [{"channel": "search ads", "spend_usd": 1200.5}]}
    assert fake_services.executor.calls[-1] == (
        "SELECT c.channel FROM marketing.campaigns c WHERE c.start_date >= %(start)s", {"start": "2026-07-01"})


async def test_run_sql_rejects_other_schemas_and_missing_params(fake_services):
    other = await run_sql("marketing", "SELECT * FROM trading.trades")
    assert "may only read the 'marketing' schema" in other["error"]
    missing = await run_sql("marketing", "SELECT * FROM marketing.campaigns c WHERE c.entity_id = :entity_id")
    assert missing == {"error": "No value passed for :entity_id"}
    assert fake_services.executor.calls == []
