"""Marketing queries, from the Nimbus data team.

Each function runs one read-only query on the marketing schema. It returns
{"row_count", "truncated", "rows"}, or {"error": "..."} if something is wrong.
Dates are strings in YYYY-MM-DD format, and both ends of a range are included.
Entity ids are NM-UK, NM-SG, NM-AE and NM-INTL.
"""

from __future__ import annotations

from devfest_agents.tools.sql_query import run_sql

CAMPAIGN_PERFORMANCE = """
WITH spend AS (
    SELECT s.campaign_id, SUM(s.spend_usd) AS spend_usd, SUM(s.impressions) AS impressions, SUM(s.clicks) AS clicks
    FROM marketing.campaign_spend s
    WHERE s.spend_date BETWEEN :start_date AND :end_date
    GROUP BY s.campaign_id
), signups AS (
    SELECT g.campaign_id, COUNT(*) AS signups
    FROM marketing.signups g
    WHERE g.signup_date BETWEEN :start_date AND :end_date
    GROUP BY g.campaign_id
)
SELECT c.campaign_id, c.name, c.entity_id, c.channel,
       COALESCE(sp.spend_usd, 0) AS spend_usd,
       COALESCE(sp.impressions, 0) AS impressions,
       COALESCE(sp.clicks, 0) AS clicks,
       COALESCE(su.signups, 0) AS signups,
       ROUND(sp.spend_usd / NULLIF(su.signups, 0), 2) AS cost_per_signup_usd
FROM marketing.campaigns c
LEFT JOIN spend sp ON sp.campaign_id = c.campaign_id
LEFT JOIN signups su ON su.campaign_id = c.campaign_id
WHERE (sp.campaign_id IS NOT NULL OR su.campaign_id IS NOT NULL)
  AND (:entity_id::text IS NULL OR c.entity_id = :entity_id)
ORDER BY spend_usd DESC
"""

CHANNEL_SUMMARY = """
WITH spend AS (
    SELECT c.channel, SUM(s.spend_usd) AS spend_usd, SUM(s.impressions) AS impressions, SUM(s.clicks) AS clicks
    FROM marketing.campaign_spend s
    JOIN marketing.campaigns c ON c.campaign_id = s.campaign_id
    WHERE s.spend_date BETWEEN :start_date AND :end_date
      AND (:entity_id::text IS NULL OR c.entity_id = :entity_id)
    GROUP BY c.channel
), signups AS (
    SELECT c.channel, COUNT(*) AS signups
    FROM marketing.signups g
    JOIN marketing.campaigns c ON c.campaign_id = g.campaign_id
    WHERE g.signup_date BETWEEN :start_date AND :end_date
      AND (:entity_id::text IS NULL OR c.entity_id = :entity_id)
    GROUP BY c.channel
)
SELECT sp.channel, sp.spend_usd, sp.impressions, sp.clicks,
       ROUND(100.0 * sp.clicks / NULLIF(sp.impressions, 0), 2) AS click_through_pct,
       COALESCE(su.signups, 0) AS signups,
       ROUND(sp.spend_usd / NULLIF(su.signups, 0), 2) AS cost_per_signup_usd
FROM spend sp
LEFT JOIN signups su ON su.channel = sp.channel
ORDER BY sp.spend_usd DESC
"""

MONTHLY_SPEND = """
WITH spend AS (
    SELECT date_trunc('month', s.spend_date)::date AS month,
           SUM(s.spend_usd) AS spend_usd, SUM(s.impressions) AS impressions, SUM(s.clicks) AS clicks
    FROM marketing.campaign_spend s
    JOIN marketing.campaigns c ON c.campaign_id = s.campaign_id
    WHERE s.spend_date BETWEEN :start_date AND :end_date
      AND (:entity_id::text IS NULL OR c.entity_id = :entity_id)
      AND (:channel::text IS NULL OR c.channel = :channel)
    GROUP BY 1
), signups AS (
    SELECT date_trunc('month', g.signup_date)::date AS month, COUNT(*) AS signups
    FROM marketing.signups g
    JOIN marketing.campaigns c ON c.campaign_id = g.campaign_id
    WHERE g.signup_date BETWEEN :start_date AND :end_date
      AND (:entity_id::text IS NULL OR c.entity_id = :entity_id)
      AND (:channel::text IS NULL OR c.channel = :channel)
    GROUP BY 1
)
SELECT sp.month, sp.spend_usd, sp.impressions, sp.clicks,
       COALESCE(su.signups, 0) AS signups,
       ROUND(sp.spend_usd / NULLIF(su.signups, 0), 2) AS cost_per_signup_usd
FROM spend sp
LEFT JOIN signups su ON su.month = sp.month
ORDER BY sp.month
"""

ENTITY_SUMMARY = """
WITH spend AS (
    SELECT c.entity_id, SUM(s.spend_usd) AS spend_usd, SUM(s.clicks) AS clicks
    FROM marketing.campaign_spend s
    JOIN marketing.campaigns c ON c.campaign_id = s.campaign_id
    WHERE s.spend_date BETWEEN :start_date AND :end_date
    GROUP BY c.entity_id
), signups AS (
    SELECT c.entity_id, COUNT(*) AS signups
    FROM marketing.signups g
    JOIN marketing.campaigns c ON c.campaign_id = g.campaign_id
    WHERE g.signup_date BETWEEN :start_date AND :end_date
    GROUP BY c.entity_id
)
SELECT sp.entity_id, sp.spend_usd, sp.clicks,
       COALESCE(su.signups, 0) AS signups,
       ROUND(sp.spend_usd / NULLIF(su.signups, 0), 2) AS cost_per_signup_usd
FROM spend sp
LEFT JOIN signups su ON su.entity_id = sp.entity_id
ORDER BY sp.spend_usd DESC
"""

CAMPAIGNS = """
SELECT c.campaign_id, c.name, c.entity_id, c.channel, c.start_date, c.end_date
FROM marketing.campaigns c
WHERE (:entity_id::text IS NULL OR c.entity_id = :entity_id)
  AND (:name_contains::text IS NULL OR c.name ILIKE '%' || :name_contains || '%')
ORDER BY c.start_date, c.campaign_id
"""


async def fetch_campaign_performance(start_date: str, end_date: str, entity_id: str | None = None) -> dict:
    # one row per campaign that spent money or brought in a client in the range
    return await run_sql("marketing", CAMPAIGN_PERFORMANCE, start_date=start_date, end_date=end_date,
                         entity_id=entity_id)


async def fetch_channel_summary(start_date: str, end_date: str, entity_id: str | None = None) -> dict:
    # one row per ad channel: spend, impressions, clicks, CTR, sign-ups, cost per sign-up
    return await run_sql("marketing", CHANNEL_SUMMARY, start_date=start_date, end_date=end_date,
                         entity_id=entity_id)


async def fetch_monthly_spend(start_date: str, end_date: str, entity_id: str | None = None,
                              channel: str | None = None) -> dict:
    # one row per month; channel is e.g. "search ads", "social ads", "video ads", "app-store ads", "affiliate network"
    return await run_sql("marketing", MONTHLY_SPEND, start_date=start_date, end_date=end_date,
                         entity_id=entity_id, channel=channel)


async def fetch_entity_summary(start_date: str, end_date: str) -> dict:
    # one row per entity that ran campaigns in the range
    return await run_sql("marketing", ENTITY_SUMMARY, start_date=start_date, end_date=end_date)


async def fetch_campaigns(entity_id: str | None = None, name_contains: str | None = None) -> dict:
    # the campaign list with first and last spend dates; name_contains="Nimbus Go" finds the launch campaigns
    return await run_sql("marketing", CAMPAIGNS, entity_id=entity_id, name_contains=name_contains)
