-- =============================================================================
-- 00_roles.sql  -  roles, schemas and privileges for the Nimbus Markets demo DB
-- Runs once, as the postgres superuser, when the data volume is empty
-- (docker-entrypoint-initdb.d). Files run in name order: 00 -> 10 -> 20 -> 30 -> 40.
-- =============================================================================

-- All timestamps are interpreted and displayed in UTC (close_time::date etc.).
-- (current_database() so a different POSTGRES_DB still works.)
DO $$ BEGIN
  EXECUTE format('ALTER DATABASE %I SET timezone TO %L', current_database(), 'UTC');
END $$;
SET timezone TO 'UTC';

-- ---------------------------------------------------------------------------
-- Roles
--   app       the FastAPI backend: owns the tools registry, can read finance +
--             trading (schema browser, sample rows).
--   agent_ro  used to EXECUTE agent tool SQL: SELECT on finance + trading only,
--             no access to tools, read-only transactions, 5 s statement timeout.
-- ---------------------------------------------------------------------------
CREATE ROLE app LOGIN PASSWORD 'app';
CREATE ROLE agent_ro LOGIN PASSWORD 'agent_ro';

-- Defence in depth for the agent role (the backend also enforces these).
ALTER ROLE agent_ro SET default_transaction_read_only = on;
ALTER ROLE agent_ro SET statement_timeout = '5s';
ALTER ROLE agent_ro SET search_path = '';
ALTER ROLE app SET search_path = tools, public;

-- Nobody but the owner may create objects in public; no default access to the DB
-- beyond CONNECT for our two roles.
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
DO $$ BEGIN
  EXECUTE format('REVOKE ALL ON DATABASE %I FROM PUBLIC', current_database());
  EXECUTE format('GRANT CONNECT, TEMPORARY ON DATABASE %I TO app', current_database());
  EXECUTE format('GRANT CONNECT ON DATABASE %I TO agent_ro', current_database());
END $$;

-- ---------------------------------------------------------------------------
-- Schemas
-- ---------------------------------------------------------------------------
CREATE SCHEMA finance;            -- owned by postgres, read-only for app + agent_ro
CREATE SCHEMA trading;            -- owned by postgres, read-only for app + agent_ro
CREATE SCHEMA tools AUTHORIZATION app;

REVOKE ALL ON SCHEMA finance, trading, tools FROM PUBLIC;

GRANT USAGE ON SCHEMA finance, trading TO app, agent_ro;
GRANT USAGE, CREATE ON SCHEMA tools TO app;
-- agent_ro intentionally gets nothing on schema tools.

-- (No FOR ROLE clause: applies to objects created by the current role, i.e. the
-- superuser running these init scripts, whatever POSTGRES_USER is.)
-- Tables created later by postgres in finance/trading become SELECT-able
-- automatically (10_finance.sql / 20_trading.sql run after this file).
ALTER DEFAULT PRIVILEGES IN SCHEMA finance GRANT SELECT ON TABLES TO app, agent_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA trading GRANT SELECT ON TABLES TO app, agent_ro;

-- Anything postgres creates in tools is usable by app (30_tools.sql also
-- transfers ownership to app explicitly).
ALTER DEFAULT PRIVILEGES IN SCHEMA tools GRANT ALL ON TABLES TO app;
ALTER DEFAULT PRIVILEGES IN SCHEMA tools GRANT ALL ON SEQUENCES TO app;
ALTER DEFAULT PRIVILEGES IN SCHEMA tools GRANT EXECUTE ON FUNCTIONS TO app;

COMMENT ON ROLE app IS 'Backend service role: owns schema tools (tool registry), SELECT on finance and trading for schema browsing.';
COMMENT ON ROLE agent_ro IS 'Executes agent tool SQL: SELECT on finance and trading only, read-only transactions, 5s statement timeout, no access to tools.';
