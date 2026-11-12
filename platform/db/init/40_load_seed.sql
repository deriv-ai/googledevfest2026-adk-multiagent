-- =============================================================================
-- 40_load_seed.sql  -  load the committed synthetic CSVs (db/seed -> /seed)
-- Server-side COPY: runs as the init superuser, files are mounted read-only.
-- Parents before children so foreign keys are satisfied. Re-run by wiping the
-- data volume (make reset).
-- =============================================================================
SET timezone TO 'UTC';

\echo 'Loading synthetic Nimbus Markets seed data from /seed ...'

COPY finance.entities (entity_id, name, country, currency)
    FROM '/seed/finance_entities.csv' WITH (FORMAT csv, HEADER true);
COPY finance.accounts (account_code, account_name, account_type, category)
    FROM '/seed/finance_accounts.csv' WITH (FORMAT csv, HEADER true);
COPY finance.fx_rates (rate_date, currency, usd_rate)
    FROM '/seed/finance_fx_rates.csv' WITH (FORMAT csv, HEADER true);
COPY finance.gl_entries (entry_id, entry_date, entity_id, account_code, amount_local, currency, amount_usd, description)
    FROM '/seed/finance_gl_entries.csv' WITH (FORMAT csv, HEADER true);
COPY finance.budgets (month, entity_id, account_code, budget_usd)
    FROM '/seed/finance_budgets.csv' WITH (FORMAT csv, HEADER true);

COPY trading.clients (client_id, full_name, country, segment, signup_date, risk_level)
    FROM '/seed/trading_clients.csv' WITH (FORMAT csv, HEADER true);
COPY trading.instruments (symbol, name, asset_class)
    FROM '/seed/trading_instruments.csv' WITH (FORMAT csv, HEADER true);
COPY trading.trades (trade_id, client_id, symbol, side, quantity, open_price, close_price, open_time, close_time,
                     notional_usd, pnl_usd, commission_usd, status)
    FROM '/seed/trading_trades.csv' WITH (FORMAT csv, HEADER true);
COPY trading.daily_prices (symbol, price_date, open, high, low, close, volume)
    FROM '/seed/trading_daily_prices.csv' WITH (FORMAT csv, HEADER true);

COPY marketing.campaigns (campaign_id, name, entity_id, channel, start_date, end_date)
    FROM '/seed/marketing_campaigns.csv' WITH (FORMAT csv, HEADER true);
COPY marketing.campaign_spend (spend_id, campaign_id, spend_date, spend_usd, impressions, clicks)
    FROM '/seed/marketing_campaign_spend.csv' WITH (FORMAT csv, HEADER true);
COPY marketing.signups (client_id, campaign_id, signup_date)
    FROM '/seed/marketing_signups.csv' WITH (FORMAT csv, HEADER true);

ANALYZE finance.entities, finance.accounts, finance.fx_rates, finance.gl_entries, finance.budgets,
        trading.clients, trading.instruments, trading.trades, trading.daily_prices,
        marketing.campaigns, marketing.campaign_spend, marketing.signups;

\echo 'Seed data loaded.'
