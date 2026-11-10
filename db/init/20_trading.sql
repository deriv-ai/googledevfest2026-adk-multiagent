-- =============================================================================
-- 20_trading.sql  -  schema "trading": clients, instruments, trades, prices (SYNTHETIC)
-- =============================================================================
SET timezone TO 'UTC';

COMMENT ON SCHEMA trading IS
'Brokerage activity of Nimbus Markets, a FICTIONAL broker. 100% synthetic: client names are random first/last-name combinations, '
'prices are seeded random walks and every trade is generated (scripts/generate_synthetic_data.py) - no real market data, no real people. '
'trading.clients open positions (trading.trades) in trading.instruments (generic FX pairs, crypto, commodities and broad indices); '
'trading.daily_prices holds synthetic daily OHLC per instrument. Money columns ending in _usd are US dollars. Timestamps are UTC. '
'Used by the trading_agent. Link to finance via trading.clients.country -> finance entity (mapping on that column''s comment).';

-- ---------------------------------------------------------------------------
CREATE TABLE trading.clients (
    client_id   text PRIMARY KEY,
    full_name   text NOT NULL,
    country     text NOT NULL,
    segment     text NOT NULL CHECK (segment IN ('retail', 'pro', 'vip')),
    signup_date date NOT NULL,
    risk_level  text NOT NULL CHECK (risk_level IN ('low', 'medium', 'high'))
);
COMMENT ON TABLE trading.clients IS
'One row per (fictional) client account, ~600 rows. Names are synthetic combinations - not real people. '
'Segment drives trade size (vip >> pro >> retail) and commission discounts; risk_level is the onboarding risk rating. '
'"New clients" in a period = clients whose signup_date falls in it; "active clients" = distinct client_id in trading.trades for the period.';
COMMENT ON COLUMN trading.clients.client_id   IS 'Client id, primary key, format C00001..C00600. Join key for trading.trades.client_id.';
COMMENT ON COLUMN trading.clients.full_name   IS 'Synthetic display name (random first + last name). Not a real person.';
COMMENT ON COLUMN trading.clients.country     IS
'ISO 3166-1 alpha-2 country of residence. Also decides the booking entity in finance: '
'GB -> NM-UK; SG, MY, TH, ID, VN, PH -> NM-SG; AE, SA, QA, KW, BH, OM -> NM-AE; any other country -> NM-INTL. '
'SQL: CASE WHEN country = ''GB'' THEN ''NM-UK'' WHEN country IN (''SG'',''MY'',''TH'',''ID'',''VN'',''PH'') THEN ''NM-SG'' WHEN country IN (''AE'',''SA'',''QA'',''KW'',''BH'',''OM'') THEN ''NM-AE'' ELSE ''NM-INTL'' END.';
COMMENT ON COLUMN trading.clients.segment     IS 'Client tier: retail, pro or vip. vip clients trade the largest notionals and get the biggest commission discount (0.6x), pro 0.8x, retail 1.0x.';
COMMENT ON COLUMN trading.clients.signup_date IS 'Date the account was opened. Some clients signed up before the data window (existing book). A client has no trades before signup_date.';
COMMENT ON COLUMN trading.clients.risk_level  IS 'Onboarding risk rating: low, medium or high. Use it for risk-mix breakdowns (e.g. share of commission from high-risk clients).';

CREATE INDEX clients_country_idx ON trading.clients (country);
CREATE INDEX clients_segment_idx ON trading.clients (segment);

-- ---------------------------------------------------------------------------
CREATE TABLE trading.instruments (
    symbol      text PRIMARY KEY,
    name        text NOT NULL,
    asset_class text NOT NULL CHECK (asset_class IN ('forex', 'crypto', 'commodities', 'indices'))
);
COMMENT ON TABLE trading.instruments IS
'Tradable instruments (16 rows): generic, well-known public market symbols - FX pairs, Bitcoin/Ether, gold/silver/oil and broad equity indices. '
'No single-company stocks. All prices for them in this database are SYNTHETIC. Use name (e.g. "Bitcoin", "Gold") as the search term for news.';
COMMENT ON COLUMN trading.instruments.symbol      IS 'Ticker-style symbol, primary key: EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD, EURGBP, BTCUSD, ETHUSD, XAUUSD, XAGUSD, USOIL, US100, US500, GER40, UK100, JP225.';
COMMENT ON COLUMN trading.instruments.name        IS 'Plain-English name, e.g. "Bitcoin", "Gold", "US Tech 100 Index", "Euro / US Dollar". Good keyword for news searches.';
COMMENT ON COLUMN trading.instruments.asset_class IS 'One of: forex, crypto, commodities, indices. Commission rates differ by asset class (crypto highest).';

-- ---------------------------------------------------------------------------
CREATE TABLE trading.trades (
    trade_id       bigint        PRIMARY KEY,
    client_id      text          NOT NULL REFERENCES trading.clients (client_id),
    symbol         text          NOT NULL REFERENCES trading.instruments (symbol),
    side           text          NOT NULL CHECK (side IN ('buy', 'sell')),
    quantity       numeric(18,4) NOT NULL CHECK (quantity > 0),
    open_price     numeric(18,6) NOT NULL,
    close_price    numeric(18,6),
    open_time      timestamptz   NOT NULL,
    close_time     timestamptz,
    notional_usd   numeric(18,2) NOT NULL,
    pnl_usd        numeric(18,2),
    commission_usd numeric(18,2),
    status         text          NOT NULL CHECK (status IN ('open', 'closed')),
    CHECK ((status = 'closed') = (close_time IS NOT NULL))
);
COMMENT ON TABLE trading.trades IS
'One row per client position (synthetic, ~20k rows). A trade opens at open_time and, when closed, has close_time, close_price, pnl_usd and commission_usd. '
'Open trades (status = ''open'', only at the very end of the window) have NULL close_* / pnl_usd / commission_usd. '
'Activity is normally bucketed by close_time (that is when commission is earned and booked to finance account 4100), e.g. WHERE close_time >= ''2026-07-01'' AND close_time < ''2026-10-01''. '
'Volume = SUM(notional_usd). Revenue to Nimbus = commission_usd; pnl_usd is the CLIENT''s result (client losses are not Nimbus revenue in this model).';
COMMENT ON COLUMN trading.trades.trade_id       IS 'Trade id, primary key, increasing with open_time.';
COMMENT ON COLUMN trading.trades.client_id      IS 'FK -> trading.clients.client_id. Join clients for segment, country (-> finance entity) and risk_level.';
COMMENT ON COLUMN trading.trades.symbol         IS 'FK -> trading.instruments.symbol. Join instruments for name and asset_class.';
COMMENT ON COLUMN trading.trades.side           IS 'buy (long) or sell (short).';
COMMENT ON COLUMN trading.trades.quantity       IS 'Size in units of the base asset (coins, ounces, barrels, index units, or base-currency units for FX). Prefer notional_usd for volume.';
COMMENT ON COLUMN trading.trades.open_price     IS 'Synthetic entry price in the instrument''s quote terms (USD for most; JPY/CAD for USDJPY/USDCAD).';
COMMENT ON COLUMN trading.trades.close_price    IS 'Synthetic exit price; NULL while status = ''open''.';
COMMENT ON COLUMN trading.trades.open_time      IS 'When the position was opened (timestamptz, UTC).';
COMMENT ON COLUMN trading.trades.close_time     IS 'When the position was closed (timestamptz, UTC); NULL while open. Use close_time::date or date_trunc(''month'', close_time) to bucket activity; this matches how the GL books commission.';
COMMENT ON COLUMN trading.trades.notional_usd   IS 'Trade size in US dollars at open (quantity x open_price, or quantity for USD-base FX pairs). SUM(notional_usd) = trading volume. Always use this instead of quantity * open_price.';
COMMENT ON COLUMN trading.trades.pnl_usd        IS 'Client profit (+) or loss (-) in USD on the closed position, before commission. NULL while open. Win rate = share of closed trades with pnl_usd > 0.';
COMMENT ON COLUMN trading.trades.commission_usd IS 'Commission Nimbus earned on the trade in USD (positive), charged at close; NULL while open. SUM per month and entity reconciles with finance.gl_entries account 4100 (Trading commission).';
COMMENT ON COLUMN trading.trades.status         IS 'open or closed. Only closed trades have close_time, pnl_usd and commission_usd.';

CREATE INDEX trades_close_time_idx ON trading.trades (close_time);
CREATE INDEX trades_open_time_idx  ON trading.trades (open_time);
CREATE INDEX trades_client_id_idx  ON trading.trades (client_id);
CREATE INDEX trades_symbol_idx     ON trading.trades (symbol, close_time);

-- ---------------------------------------------------------------------------
CREATE TABLE trading.daily_prices (
    symbol     text          NOT NULL REFERENCES trading.instruments (symbol),
    price_date date          NOT NULL,
    open       numeric(18,6) NOT NULL,
    high       numeric(18,6) NOT NULL,
    low        numeric(18,6) NOT NULL,
    close      numeric(18,6) NOT NULL,
    volume     bigint        NOT NULL,
    PRIMARY KEY (symbol, price_date)
);
COMMENT ON TABLE trading.daily_prices IS
'Synthetic daily OHLC candles per instrument (seeded random walk, NOT real market prices). Crypto trades 7 days a week; other asset classes have weekday rows only. '
'Monthly return example: last close of month / first open of month - 1. Each trade''s prices fall inside that day''s low-high range.';
COMMENT ON COLUMN trading.daily_prices.symbol     IS 'FK -> trading.instruments.symbol.';
COMMENT ON COLUMN trading.daily_prices.price_date IS 'Trading date (UTC).';
COMMENT ON COLUMN trading.daily_prices.open       IS 'Synthetic opening price (quote terms of the instrument).';
COMMENT ON COLUMN trading.daily_prices.high       IS 'Synthetic daily high.';
COMMENT ON COLUMN trading.daily_prices.low        IS 'Synthetic daily low.';
COMMENT ON COLUMN trading.daily_prices.close      IS 'Synthetic closing price; next row''s open equals this close.';
COMMENT ON COLUMN trading.daily_prices.volume     IS 'Synthetic market-wide volume in units of the instrument (NOT Nimbus client volume - use SUM(trades.notional_usd) for that).';

CREATE INDEX daily_prices_date_idx ON trading.daily_prices (price_date);
