"""marketing_agent: answers Vernon's campaign questions.

The data team's queries are in marketing_queries.py. You turn them into tools,
give the tools to an agent, and plug the agent into the orchestrator.
The exercises in exercises/ walk you through it.
"""

from __future__ import annotations

from typing import Any

from google.adk.agents import LlmAgent

from . import marketing_queries as queries
from devfest_agents.agents.common import GENERATION, static_instruction  # noqa: F401 - build() uses them (exercise 2)

NAME = "marketing_agent"
LABEL = "Marketing agent"
DATASOURCE = "marketing"

# Exercise 2: the pitch other agents read when deciding whether to send this agent work.
DESCRIPTION = ""


# Exercise 1: write two tools here, one per campaign and one per ad channel.


# ---------------------------------------------------------------------------
# Ready-made tools. They wrap the data team's other queries the same way yours do,
# so you don't have to type them out. Give them to your agent in exercise 2.
# ---------------------------------------------------------------------------
async def monthly_spend(start_date: str, end_date: str, entity_id: str | None = None,
                        channel: str | None = None) -> dict:
    """Campaign spend, impressions, clicks and sign-ups per calendar month.

    One row per month that had spend: month (first day of the month), spend_usd, impressions,
    clicks, signups and cost_per_signup_usd. Use it for trends and month-by-month questions,
    such as "what did NM-SG spend each month this year?".

    Args:
        start_date: First day, YYYY-MM-DD.
        end_date: Last day (inclusive), YYYY-MM-DD.
        entity_id: Only this entity: NM-UK, NM-SG, NM-AE or NM-INTL. Omit for all.
        channel: Only this channel: "search ads", "social ads", "video ads", "app-store ads" or
            "affiliate network". Omit for all.
    """
    return await queries.fetch_monthly_spend(start_date, end_date, entity_id, channel)


async def entity_summary(start_date: str, end_date: str) -> dict:
    """Campaign spend, clicks and sign-ups per entity for a date range.

    One row per entity that ran campaigns: entity_id, spend_usd, clicks, signups and
    cost_per_signup_usd, biggest spender first. Use it for "which entity spent the most?".

    Args:
        start_date: First day, YYYY-MM-DD.
        end_date: Last day (inclusive), YYYY-MM-DD.
    """
    return await queries.fetch_entity_summary(start_date, end_date)


async def campaign_list(entity_id: str | None = None, name_contains: str | None = None) -> dict:
    """The campaigns themselves, with no figures: who ran them, on which channel, and when.

    One row per campaign: campaign_id, name, entity_id, channel, start_date and end_date (the
    planned dates). Use it to find campaigns by name, for example name_contains="Nimbus Go".

    Args:
        entity_id: Only this entity: NM-UK, NM-SG, NM-AE or NM-INTL. Omit for all.
        name_contains: Part of the campaign name, any case. Omit for all campaigns.
    """
    return await queries.fetch_campaigns(entity_id, name_contains)


READY_MADE_TOOLS = [monthly_spend, entity_summary, campaign_list]


# Exercise 2: build the agent. Every specialist has this same build(services, model) signature,
# so the team can build them all the same way. Finance and trading use `services` to reach the
# tool registry in the database; your agent doesn't need it.
def build(services: Any, model: Any) -> LlmAgent:
    raise NotImplementedError("marketing_agent.build() is exercise 2")
