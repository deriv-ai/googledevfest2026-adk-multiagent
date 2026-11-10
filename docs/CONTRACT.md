# System contract

The reference for how the pieces of this demo talk to each other: services and
ports, environment variables, the database schema, the tool spec format, the news
MCP tools, the HTTP API and the chat SSE events. Read it if you want to build your
own tools, write another frontend, or swap a component out.

All data is 100% synthetic (fictional company "Nimbus Markets").

## Ports / services (compose.yaml)
All ports are published on `127.0.0.1` only (`BIND_ADDRESS` in `.env`); there is no auth, so keep it local.

| service | port | notes |
|---|---|---|
| `db` | 5432 | postgres:17-alpine, DB `nimbus`, superuser `postgres`/`postgres` (env overridable) |
| `news-mcp` | 8001 | FastMCP streamable HTTP, endpoint `http://news-mcp:8001/mcp` |
| `app` | 8080 | FastAPI: `/api/*` + built SPA from `STATIC_DIR` |
| `adk-web` | 8000 | `adk web --host 0.0.0.0 --port 8000 /app/src/devfest_agents/adk_apps` (same image as app). Discovered via `src/devfest_agents/adk_apps/nimbus/__init__.py` (`from . import agent`) + `agent.py` exporting `root_agent`. |

## Environment variables (read by `config.py`, provided via `.env` + compose)
| var | default | meaning |
|---|---|---|
| `LITELLM_GEMINI_API_KEY` | – | LLM key. **Takes precedence.** Used with `OPENAI_BASE_URL` (LiteLLM proxy mode) or alone as a Gemini key |
| `GEMINI_API_KEY` | – | Fallback LLM key (Google AI Studio, direct mode). One of the two keys must be set |
| `OPENAI_BASE_URL` | – | Optional OpenAI-compatible LiteLLM proxy base (e.g. `https://proxy.example.com/v1`). When set → proxy mode: pass `api_base`+`api_key` to `LiteLlm`, model strings use the `openai/` prefix |
| `AGENT_MODEL` | proxy mode: `openai/gemini-3.8-flash`; direct mode: `gemini/gemini-3.8-flash` | specialists' model (LiteLLM model string) |
| `ROUTER_MODEL` | = AGENT_MODEL | main_agent + orchestrator model |
| `DATABASE_URL` | `postgresql://app:app@db:5432/nimbus` | rw on `tools` schema, read on finance/trading for schema browsing |
| `AGENT_DATABASE_URL` | `postgresql://agent_ro:agent_ro@db:5432/nimbus` | SELECT-only on finance + trading |
| `NEWS_MCP_URL` | `http://news-mcp:8001/mcp` | |
| `STATIC_DIR` | `/app/static` | built SPA |
| `STARTER_TOOLS_PATH` | `/app/seed/starter_tools.yaml` | upserted on startup (insert-if-missing) |
| `TOOL_MAX_ROWS` | `200` | |
| `MAX_DELEGATIONS` | `4` | orchestrator cap per turn |
| `LOG_LEVEL` | `INFO` | |
| `LLM_TIMEOUT_SECONDS` / `LLM_NUM_RETRIES` | `60` / `2` | Per LLM call timeout + retries (fail fast on proxy hiccups) |
| `LLM_REASONING_EFFORT` | `low` (empty = provider default) | Optional `low`/`medium`/`high`, passed to LiteLLM as `reasoning_effort` (with `drop_params`). Lower = faster answers on Gemini 3.x reasoning models. |

## Database (one DB `nimbus`, three schemas, DDL in `db/init/`)
Roles (created in `db/init/00_roles.sql`): `app` / password `app` (owner of schema `tools`,
SELECT on finance+trading); `agent_ro` / password `agent_ro` (SELECT on finance+trading only,
no access to `tools`). Every table and column gets `COMMENT ON` (the UI renders these).

### finance
- `finance.entities` (entity_id text PK e.g. `NM-UK`, name text, country text, currency char(3))
- `finance.accounts` (account_code text PK e.g. `4100`, account_name text, account_type text
  check in (`revenue`,`expense`,`asset`,`liability`,`equity`), category text)
  - revenue categories include: `Trading commission`, `Spread revenue`, `Subscription fees`, `Interest income`
  - expense categories include: `Staff costs`, `Marketing`, `Technology`, `Office & admin`, `Payment processing`, `Professional fees`
- `finance.fx_rates` (rate_date date, currency char(3), usd_rate numeric(18,8)) PK (rate_date, currency) — 1 unit of currency = usd_rate USD
- `finance.gl_entries` (entry_id bigint PK, entry_date date, entity_id → entities, account_code → accounts,
  amount_local numeric(18,2), currency char(3), amount_usd numeric(18,2), description text)
  - **sign convention: revenue positive, expense positive (amounts are magnitudes); account_type tells you which**
- `finance.budgets` (month date (first day of month), entity_id → entities, account_code → accounts, budget_usd numeric(18,2)) PK (month, entity_id, account_code)

### trading
- `trading.clients` (client_id text PK e.g. `C00042`, full_name text, country text, segment text check in (`retail`,`pro`,`vip`), signup_date date, risk_level text check in (`low`,`medium`,`high`))
- `trading.instruments` (symbol text PK e.g. `EURUSD`, `BTCUSD`, `XAUUSD`, `US100`; name text; asset_class text check in (`forex`,`crypto`,`commodities`,`indices`))
- `trading.trades` (trade_id bigint PK, client_id → clients, symbol → instruments, side text check in (`buy`,`sell`), quantity numeric(18,4),
  open_price numeric(18,6), close_price numeric(18,6), open_time timestamptz, close_time timestamptz (null while open),
  notional_usd numeric(18,2), pnl_usd numeric(18,2) (client PnL), commission_usd numeric(18,2), status text check in (`open`,`closed`))
- `trading.daily_prices` (symbol → instruments, price_date date, open, high, low, close numeric(18,6), volume bigint) PK (symbol, price_date)

Reconciliation property: for every month and entity, `SUM(trades.commission_usd)` for that entity's clients
≈ GL `Trading commission` revenue. Client → entity mapping: by `clients.country` (`GB`→`NM-UK`, `SG`/`MY`/… →`NM-SG`, `AE`/… → `NM-AE`, others → `NM-INTL`); documented in a column comment.

### tools
```sql
tools.tools (
  name text PRIMARY KEY CHECK (name ~ '^[a-z][a-z0-9_]{2,63}$'),
  agent text NOT NULL CHECK (agent IN ('finance','trading')),
  tool_type text NOT NULL CHECK (tool_type IN ('sql','factual')),
  title text NOT NULL,
  description text NOT NULL,
  sql_text text,                -- required when sql
  params jsonb NOT NULL DEFAULT '[]',
  answer_text text,             -- required when factual
  source text,                  -- factual citation
  enabled boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),   -- trigger keeps it fresh
  CHECK ((tool_type='sql' AND sql_text IS NOT NULL) OR (tool_type='factual' AND answer_text IS NOT NULL))
)
tools.tool_runs (id bigserial PK, name text, agent text, args jsonb, row_count int, duration_ms int, error text, created_at timestamptz default now())
```
The `tools` table starts EMPTY in SQL; the backend seeds it from `seed/starter_tools.yaml` at app startup.

## Tool spec (YAML seed + API JSON share this shape)
```yaml
tools:
  - name: trading_top_instruments
    agent: trading                 # finance | trading
    tool_type: sql                 # sql | factual
    title: Top instruments by commission, volume or client PnL
    description: >                 # written for the LLM
      ...
    params:                        # sql only; [] for factual
      - name: start_date
        type: date                 # date | string | integer | number | boolean
        required: true
        description: Inclusive start date, YYYY-MM-DD
        example: "2026-07-01"      # used by Test run + integration test (required for required params)
      - name: metric
        type: string
        required: false
        default: commission
        enum: [volume, commission, client_pnl]
      - name: limit
        type: integer
        required: false
        default: 10
        min: 1
        max: 50
    sql: |                         # API JSON key is "sql" too
      SELECT ... WHERE t.close_time::date BETWEEN :start_date AND :end_date ... LIMIT :limit
    # factual tools instead: answer: "markdown", source: "Nimbus Finance Handbook §2"
```
- Placeholders are `:name` (`::casts` are not placeholders). Declared params must match placeholders exactly.
- SQL: single SELECT/WITH, may only reference the tool's own agent schema (`finance.` or `trading.`), fully schema-qualified table names.
- Optional params with no default are passed as SQL NULL — write `(:entity_id IS NULL OR g.entity_id = :entity_id)`. Backend binds with explicit casts based on param type so NULL typing works.

Starter tools (the 6 seeded on first start): `finance_monthly_pnl`, `finance_revenue_breakdown`,
`finance_budget_vs_actual`, `trading_activity_summary`, `trading_top_instruments`, `trading_client_segment_performance`.

## News MCP server — tools exposed to the news agent
- `latest_headlines(topic: str = "markets", limit: int = 10) -> list[{title, link, source, published, summary}]`
  topics: `markets`, `crypto`, `forex`, `commodities`, `economy`
- `search_news(query: str, limit: int = 10) -> same shape` (Google News RSS search)
- `list_feeds() -> list[{topic, url, items_cached, last_polled}]`
Background listener polls topic feeds every `NEWS_POLL_SECONDS` (default 300). Fail soft: on network error (or no results) the tools return a single-item list `[{"note": "..."}]` instead of raising. Implemented with mcp 2.x `MCPServer` (the v2 name of FastMCP), stateless streamable HTTP; `GET /mcp` answers 405 immediately (cheap liveness probe), `GET /healthz` returns JSON.
Compose container names: `nimbus-db`, `nimbus-news-mcp`, `nimbus-app`, `nimbus-adk-web` (`make seed-tools` execs into `nimbus-app`).

## HTTP API (all JSON, base `/api`)

### Health / graph
- `GET /api/health` → `{"ok": true, "db": "ok"|"error", "news_mcp": "ok"|"error", "llm_key": "configured"|"missing", "llm_mode": "proxy"|"direct", "model": "...", "router_model": "..."}  (never expose key or base URL)`
- `GET /api/graph` →
```json
{"agents": [
   {"id":"main_agent","label":"Main agent","role":"root","description":"...","model":"..."},
   {"id":"orchestrator","label":"Orchestrator","role":"router","parent":"main_agent",...},
   {"id":"finance_agent","label":"Finance agent","role":"specialist","parent":"orchestrator","datasource":"finance"},
   {"id":"trading_agent", ... "datasource":"trading"},
   {"id":"news_agent", ... "datasource":"internet"}],
 "tools": [{"name":"finance_monthly_pnl","agent":"finance_agent","tool_type":"sql","title":"..."},
           {"name":"latest_headlines","agent":"news_agent","tool_type":"mcp","title":"..."}],
 "datasources": [{"id":"finance","label":"finance schema"},{"id":"trading","label":"trading schema"},{"id":"internet","label":"Internet (RSS)"}]}
```

### Chat (SSE over POST)
`POST /api/chat` body `{"conversation_id": "uuid", "message": "text"}` → `text/event-stream`.
Each frame: `data: <json>\n\n`; keepalive comments `: ping\n\n`. Event JSON (`ts` = epoch ms on all):
```
{"type":"start","conversation_id":"..."}
{"type":"agent_start","agent":"orchestrator","invocation_id":"..."}
{"type":"agent_end","agent":"orchestrator","invocation_id":"...","ms":1234}
{"type":"tool_call","agent":"orchestrator","tool":"trading_agent","call_id":"c1","args":{"request":"..."},"kind":"agent"}   // kind: agent | sql | factual | mcp
{"type":"tool_result","agent":"orchestrator","tool":"trading_agent","call_id":"c1","ms":2100,"kind":"agent","ok":true,"row_count":null,"error":null,"preview":"first ~300 chars / rows"}
{"type":"answer","text":"markdown","route":["main_agent","orchestrator","trading_agent","trading_top_instruments"],"elapsed_ms":5400}
{"type":"error","message":"..."}
```
A `tool_call` with `kind:"agent"` is a delegation edge from `agent` → `tool`. Others are leaf tool nodes under `agent`.
Parallel fan-out = several `tool_call`s before their `tool_result`s.
- `POST /api/chat/reset` body `{"conversation_id"}` → `{"ok":true}`
- `GET /api/chat/examples` → `[{"label":"Finance","prompt":"..."}, ...]`

### Tools
- `GET /api/tools?agent=&q=` → `[{name, agent, tool_type, title, description, enabled, params, sql, answer, source, updated_at, last_run: {created_at, row_count, duration_ms, error}|null}]`
- `GET /api/tools/{name}` → same object + `"runs": [last 10 tool_runs]`
- `POST /api/tools` body = tool spec JSON (keys as YAML; `sql`, `answer`, `source`) → 201 tool object; 409 if name exists; 422 `{"detail": "...", "errors": ["..."]}` on validation
- `PUT /api/tools/{name}` → updated object (name immutable)
- `PATCH /api/tools/{name}/enabled` body `{"enabled": bool}`
- `DELETE /api/tools/{name}` → `{"ok": true}`
- `POST /api/tools/test` body = tool spec + optional `"args": {...}` (defaults to params' `example`/`default`) →
```json
{"ok": true, "errors": [], "declaration": {"name":"...","description":"...","parameters":{...JSON schema the LLM sees...}},
 "result": {"columns":["symbol",...], "rows":[[...],...], "row_count": 10, "truncated": false, "duration_ms": 12}
           | {"answer":"markdown","source":"..."}}
```
  On lint/exec failure: `{"ok": false, "errors": ["..."], "declaration": ... or null, "result": null}` (HTTP 200).
- There is no placeholder endpoint: the UI extracts `:name` placeholders itself with the regex `(?<!:):([a-zA-Z_][a-zA-Z0-9_]*)`.

### Schema
- `GET /api/schema` → `{"schemas":[{"name":"finance","comment":"..."},{"name":"trading",...},{"name":"tools",...}]}`
- `GET /api/schema/{schema}` →
```json
{"name":"finance","comment":"...","tables":[{"name":"gl_entries","comment":"...","row_count":15000,
  "columns":[{"name":"entry_id","type":"bigint","nullable":false,"pk":true,"fk":null,"comment":"..."},
             {"name":"entity_id","type":"text","nullable":false,"pk":false,"fk":{"table":"entities","column":"entity_id"},"comment":"..."}]}]}
```
- `GET /api/schema/{schema}/{table}/sample?limit=5` → `{"columns":[...],"rows":[[...]]}` (limit ≤ 50)

Errors: non-2xx JSON `{"detail": "..."}`.

## SPA build
- `web/` is a Vite + React 18 + TS + Tailwind 4 app. `npm ci && npm run build` → `web/dist/`.
- Dev: `npm run dev` on :5173 proxies `/api` → `http://localhost:8080`.
- The app image copies `web/dist` → `/app/static`; FastAPI serves `/assets/*` and falls back to `index.html` for any non-`/api` path.

## LLM notes
- Any LiteLLM model string works (`gemini/...` direct, `openai/...` through an OpenAI-compatible proxy). Default: `gemini-3.8-flash`.
- Gemini 3.x spends **reasoning tokens** out of the completion budget: don't set a small `max_tokens` (a tiny cap returns empty answers). `LLM_REASONING_EFFORT=low` (the default) keeps cross-agent answers around 20-35 s.
- `.env` values may be quoted (`KEY="value"`); both compose implementations strip the quotes. `.env` is gitignored and excluded from images; `.env.example` holds placeholders only.
