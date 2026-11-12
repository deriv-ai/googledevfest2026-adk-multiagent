-- =============================================================================
-- 25_marketing.sql  -  schema "marketing": campaigns, spend, sign-ups (SYNTHETIC)
-- =============================================================================
SET timezone TO 'UTC';

COMMENT ON SCHEMA marketing IS
'Performance-marketing campaigns of Nimbus Markets, a FICTIONAL broker. 100% synthetic (scripts/generate_synthetic_data.py). '
'marketing.campaigns run ads on one channel for one entity; marketing.campaign_spend holds what each campaign spent (with impressions and clicks); '
'marketing.signups credits new clients to the campaign that brought them in. Money columns ending in _usd are US dollars. '
'Used by the marketing_agent. Campaign spend reconciles with finance account 5200 (Performance marketing) to the cent.';

-- ---------------------------------------------------------------------------
CREATE TABLE marketing.campaigns (
    campaign_id text PRIMARY KEY,
    name        text NOT NULL,
    entity_id   text NOT NULL REFERENCES finance.entities (entity_id),
    channel     text NOT NULL CHECK (channel IN ('search ads', 'social ads', 'video ads', 'app-store ads', 'affiliate network')),
    start_date  date NOT NULL,
    end_date    date NOT NULL
);
COMMENT ON TABLE marketing.campaigns IS
'One row per campaign (~120 rows). A campaign is one channel for one entity for one quarter, named like "NM-UK Q3 2026 - search ads". '
'Exception: from June 2026 NM-SG runs the "Nimbus Go launch" campaigns (one per channel, named "Nimbus Go launch - <channel>") to promote the Nimbus Go app.';
COMMENT ON COLUMN marketing.campaigns.campaign_id IS 'Campaign id, primary key, format CMP-001. Join key for campaign_spend and signups.';
COMMENT ON COLUMN marketing.campaigns.name        IS 'Campaign name, e.g. "NM-UK Q3 2026 - search ads" or "Nimbus Go launch - social ads". Filter Nimbus Go with name LIKE ''Nimbus Go%''.';
COMMENT ON COLUMN marketing.campaigns.entity_id   IS 'Entity that runs and pays for the campaign: NM-UK, NM-SG, NM-AE or NM-INTL (same codes as finance.entities).';
COMMENT ON COLUMN marketing.campaigns.channel     IS 'Ad channel: search ads, social ads, video ads, app-store ads or affiliate network.';
COMMENT ON COLUMN marketing.campaigns.start_date  IS 'Date of the campaign''s first spend.';
COMMENT ON COLUMN marketing.campaigns.end_date    IS 'Date of the campaign''s last spend so far.';

-- ---------------------------------------------------------------------------
CREATE TABLE marketing.campaign_spend (
    spend_id    bigint        PRIMARY KEY,
    campaign_id text          NOT NULL REFERENCES marketing.campaigns (campaign_id),
    spend_date  date          NOT NULL,
    spend_usd   numeric(18,2) NOT NULL CHECK (spend_usd > 0),
    impressions bigint        NOT NULL,
    clicks      bigint        NOT NULL
);
COMMENT ON TABLE marketing.campaign_spend IS
'One row per ad invoice (a few per entity per month). SUM(spend_usd) = campaign spend. Bucket by spend_date, e.g. WHERE spend_date BETWEEN ''2026-07-01'' AND ''2026-09-30''. '
'Click-through rate = clicks / impressions; cost per click = spend_usd / clicks.';
COMMENT ON COLUMN marketing.campaign_spend.spend_id    IS 'Invoice id, primary key. Equals the finance.gl_entries.entry_id of the matching Performance marketing line.';
COMMENT ON COLUMN marketing.campaign_spend.campaign_id IS 'FK -> marketing.campaigns.campaign_id.';
COMMENT ON COLUMN marketing.campaign_spend.spend_date  IS 'Date the spend was booked.';
COMMENT ON COLUMN marketing.campaign_spend.spend_usd   IS 'Amount spent in USD. Matches finance account 5200 (Performance marketing) for the same entity and date.';
COMMENT ON COLUMN marketing.campaign_spend.impressions IS 'Times the ads were shown.';
COMMENT ON COLUMN marketing.campaign_spend.clicks      IS 'Clicks on the ads.';

CREATE INDEX campaign_spend_date_idx ON marketing.campaign_spend (spend_date);
CREATE INDEX campaign_spend_campaign_idx ON marketing.campaign_spend (campaign_id);

-- ---------------------------------------------------------------------------
CREATE TABLE marketing.signups (
    client_id   text PRIMARY KEY REFERENCES trading.clients (client_id),
    campaign_id text NOT NULL REFERENCES marketing.campaigns (campaign_id),
    signup_date date NOT NULL
);
COMMENT ON TABLE marketing.signups IS
'New clients credited to a campaign (~200 rows). About half of all new clients come from a campaign; the rest signed up on their own and are not in this table. '
'Cost per sign-up = SUM(campaign_spend.spend_usd) / COUNT(signups) for the same campaigns and period. All new clients (campaign or not) are in trading.clients.';
COMMENT ON COLUMN marketing.signups.client_id   IS 'The new client, primary key. Same id as trading.clients.client_id.';
COMMENT ON COLUMN marketing.signups.campaign_id IS 'FK -> marketing.campaigns.campaign_id: the campaign that brought the client in.';
COMMENT ON COLUMN marketing.signups.signup_date IS 'Date the client opened their account (same as trading.clients.signup_date).';

CREATE INDEX signups_campaign_idx ON marketing.signups (campaign_id);
CREATE INDEX signups_date_idx ON marketing.signups (signup_date);
