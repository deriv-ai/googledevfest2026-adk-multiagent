"""The data team's marketing queries: guarded SQL that reaches run_sql with the right values."""

import pytest

from my_agent import marketing_queries
from devfest_agents.tools.sql_guard import check_sql

QUERIES = ["CAMPAIGN_PERFORMANCE", "CHANNEL_SUMMARY", "MONTHLY_SPEND", "ENTITY_SUMMARY", "CAMPAIGNS"]


@pytest.mark.parametrize("name", QUERIES)
def test_sql_reads_only_the_marketing_schema(name):
    assert check_sql(getattr(marketing_queries, name), "marketing") == []


async def test_fetch_functions_pass_every_placeholder(fake_services):
    await marketing_queries.fetch_monthly_spend("2026-07-01", "2026-09-30", channel="search ads")
    await marketing_queries.fetch_campaigns(name_contains="Nimbus Go")
    calls = fake_services.executor.calls
    assert calls[0][1] == {"start_date": "2026-07-01", "end_date": "2026-09-30", "entity_id": None,
                           "channel": "search ads"}
    assert calls[1][1] == {"entity_id": None, "name_contains": "Nimbus Go"}
    assert "'%%' ||" in calls[1][0]
