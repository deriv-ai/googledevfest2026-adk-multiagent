-- =============================================================================
-- 30_tools.sql  -  schema "tools": the agent tool registry (owned by role app)
-- The table starts EMPTY; the backend seeds it from seed/starter_tools.yaml at
-- app startup (insert-if-missing), and the UI adds/edits rows at runtime.
-- =============================================================================
SET timezone TO 'UTC';

COMMENT ON SCHEMA tools IS
'Tool registry for the finance and trading agents. Each row in tools.tools becomes a typed ADK FunctionTool at runtime '
'(hot-reloaded on the next question, no restart). sql tools run a parameterised SELECT as role agent_ro against their own agent''s schema; '
'factual tools return a fixed curated markdown answer. tools.tool_runs logs every execution. Not visible to agent_ro.';

-- ---------------------------------------------------------------------------
CREATE TABLE tools.tools (
    name        text        PRIMARY KEY CHECK (name ~ '^[a-z][a-z0-9_]{2,63}$'),
    agent       text        NOT NULL CHECK (agent IN ('finance', 'trading')),
    tool_type   text        NOT NULL CHECK (tool_type IN ('sql', 'factual')),
    title       text        NOT NULL,
    description text        NOT NULL,
    sql_text    text,
    params      jsonb       NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(params) = 'array'),
    answer_text text,
    source      text,
    enabled     boolean     NOT NULL DEFAULT true,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT tools_type_columns CHECK (
        (tool_type = 'sql' AND sql_text IS NOT NULL)
        OR (tool_type = 'factual' AND answer_text IS NOT NULL)
    )
);
COMMENT ON TABLE tools.tools IS
'One row per agent tool. tool_type = ''sql'' requires sql_text (+ params); tool_type = ''factual'' requires answer_text (+ source) and takes no params. '
'The (agent, enabled, max(updated_at), count) fingerprint is what the agents poll to hot-reload their toolsets.';
COMMENT ON COLUMN tools.tools.name        IS 'Function name the LLM calls; primary key, immutable. Lower snake_case, 3-64 chars, regex ^[a-z][a-z0-9_]{2,63}$, conventionally prefixed with the agent (finance_..., trading_...).';
COMMENT ON COLUMN tools.tools.agent       IS 'Owning specialist: finance or trading. sql tools may only read that agent''s schema (finance.* or trading.*).';
COMMENT ON COLUMN tools.tools.tool_type   IS 'sql = parameterised SELECT executed live; factual = fixed curated answer (definitions, policies, calendars).';
COMMENT ON COLUMN tools.tools.title       IS 'Short human title shown in the UI and in the orchestrator''s capability catalogue.';
COMMENT ON COLUMN tools.tools.description IS 'Written for the LLM: what the tool returns (columns, units), when to use it, and how it combines with other tools. This becomes the function description.';
COMMENT ON COLUMN tools.tools.sql_text    IS 'sql tools only: a single SELECT/WITH statement with :name placeholders (::casts are not placeholders) and fully schema-qualified tables. NULL for factual tools.';
COMMENT ON COLUMN tools.tools.params      IS 'JSON array of parameter specs: {name, type (date|string|integer|number|boolean), required, description, example, default, enum, min, max}. Must match the :placeholders exactly. [] for factual tools.';
COMMENT ON COLUMN tools.tools.answer_text IS 'factual tools only: the markdown answer returned verbatim. NULL for sql tools.';
COMMENT ON COLUMN tools.tools.source      IS 'factual tools: citation for the answer, e.g. "Nimbus Finance Handbook section 2". Optional for sql tools.';
COMMENT ON COLUMN tools.tools.enabled     IS 'Disabled tools are hidden from the agents but kept in the registry.';
COMMENT ON COLUMN tools.tools.created_at  IS 'When the tool was first registered.';
COMMENT ON COLUMN tools.tools.updated_at  IS 'Last modification; maintained by trigger tools.touch_updated_at. Changing it triggers a toolset reload.';

CREATE INDEX tools_agent_enabled_idx ON tools.tools (agent, enabled);

-- updated_at trigger -----------------------------------------------------------
CREATE FUNCTION tools.touch_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$;
COMMENT ON FUNCTION tools.touch_updated_at() IS 'BEFORE UPDATE trigger function: sets updated_at = now() on every change to tools.tools.';

CREATE TRIGGER tools_touch_updated_at
    BEFORE UPDATE ON tools.tools
    FOR EACH ROW EXECUTE FUNCTION tools.touch_updated_at();

-- ---------------------------------------------------------------------------
CREATE TABLE tools.tool_runs (
    id          bigserial   PRIMARY KEY,
    name        text        NOT NULL,
    agent       text,
    args        jsonb,
    row_count   integer,
    duration_ms integer,
    error       text,
    created_at  timestamptz NOT NULL DEFAULT now()
);
COMMENT ON TABLE tools.tool_runs IS 'Execution log: one row per tool invocation (from an agent or from a Test run in the UI). No FK to tools.tools so history survives deletes.';
COMMENT ON COLUMN tools.tool_runs.id          IS 'Surrogate key.';
COMMENT ON COLUMN tools.tool_runs.name        IS 'Tool name that ran (tools.tools.name at the time).';
COMMENT ON COLUMN tools.tool_runs.agent       IS 'Agent that owned the tool: finance or trading.';
COMMENT ON COLUMN tools.tool_runs.args        IS 'Validated arguments as JSON (after defaults were applied).';
COMMENT ON COLUMN tools.tool_runs.row_count   IS 'Rows returned (sql tools); NULL for factual tools or on error.';
COMMENT ON COLUMN tools.tool_runs.duration_ms IS 'Wall-clock execution time in milliseconds.';
COMMENT ON COLUMN tools.tool_runs.error       IS 'Error message if the run failed, else NULL.';
COMMENT ON COLUMN tools.tool_runs.created_at  IS 'When the run happened.';

CREATE INDEX tool_runs_name_created_idx ON tools.tool_runs (name, created_at DESC);

-- Ownership + privileges: app owns everything in tools; agent_ro gets nothing.
ALTER TABLE tools.tools OWNER TO app;
ALTER TABLE tools.tool_runs OWNER TO app;
ALTER SEQUENCE tools.tool_runs_id_seq OWNER TO app;
ALTER FUNCTION tools.touch_updated_at() OWNER TO app;
REVOKE ALL ON ALL TABLES IN SCHEMA tools FROM PUBLIC;
