# System contract

The reference for how the pieces of this demo talk to each other: services and
ports, environment variables, the database schema, the specialist interface, the tool
spec format, Python tools, the HTTP API, the chat SSE events, the workshop checks and the evals. Read it if
you want to build your own tools or agents, write another frontend, or swap a component out.

All data is 100% synthetic (fictional company "Nimbus Markets").

## Ports / services (compose.yaml)
All ports are published on `127.0.0.1` only (`BIND_ADDRESS` in `.env`); there is no auth, so keep it local.

| service | port | notes |
|---|---|---|
| `db` | 5432 | postgres:17-alpine, DB `nimbus`, superuser `postgres`/`postgres` (env overridable) |
| `app` | 8080 | FastAPI: `/api/*` + built SPA from `STATIC_DIR`. uvicorn `--reload --reload-dir /app/platform/src --reload-dir /app/my_agent` with `WATCHFILES_FORCE_POLLING=true`. Mounts `./platform/src`, `./my_agent` and `./evals` read-only at `/app/platform/src`, `/app/my_agent` and `/app/evals`. |
| `adk-web` | 8000 | `adk web --host 0.0.0.0 --port 8000 --reload_agents /app/platform/src/devfest_agents/adk_apps` (same image as app). Mounts `./platform/src` and `./my_agent` like `app`. Discovered via `src/devfest_agents/adk_apps/nimbus/__init__.py` (`from . import agent`) + `agent.py` exporting `root_agent`. |

Compose container names: `nimbus-db`, `nimbus-app`, `nimbus-adk-web`, `nimbus-news-mcp` (`make -C platform seed-tools`,
`make check-N` and `make eval` exec into `nimbus-app`). The judge starts one `judge-<name>` container per submission
on the same network.

## Environment variables (read by `config.py`, provided via `.env` + compose)
| var | default | meaning |
|---|---|---|
| `LITELLM_GEMINI_API_KEY` | – | LLM key. **Takes precedence.** Used with `OPENAI_BASE_URL` (LiteLLM proxy mode) or alone as a Gemini key |
| `GEMINI_API_KEY` | – | Fallback LLM key (Google AI Studio, direct mode). One of the two keys must be set |
| `OPENAI_BASE_URL` | – | Optional OpenAI-compatible LiteLLM proxy base (e.g. `https://proxy.example.com/v1`). When set → proxy mode: pass `api_base`+`api_key` to `LiteLlm`, model strings use the `openai/` prefix |
| `AGENT_MODEL` | proxy mode: `openai/gemini-3.7-flash`; direct mode: `gemini/gemini-3.7-flash` | specialists' model (LiteLLM model string) |
| `ROUTER_MODEL` | = AGENT_MODEL | main_agent + orchestrator model |
| `DATABASE_URL` | role `app` on `db:5432/nimbus` (see compose.yaml) | rw on `tools` schema, read on finance/trading/marketing for schema browsing |
| `AGENT_DATABASE_URL` | role `agent_ro` on `db:5432/nimbus` (see compose.yaml) | SELECT-only on finance + trading + marketing |
| `STATIC_DIR` | `/app/static` | built SPA |
| `STARTER_TOOLS_PATH` | `/app/seed/starter_tools.yaml` | upserted on startup (insert-if-missing) |
| `NEWS_MCP_URL` | `http://news-mcp:8001/mcp` | the news agent's MCP server (streamable HTTP) |
| `NEWS_POLL_SECONDS` | `300` | news-mcp only: how often it polls its RSS feeds |
| `TOOL_MAX_ROWS` | `200` | row cap for registry tools and `run_sql` |
| `MAX_DELEGATIONS` | `4` | orchestrator cap per turn |
| `LOG_LEVEL` | `INFO` | |
| `LLM_TIMEOUT_SECONDS` / `LLM_NUM_RETRIES` | `60` / `2` | Per LLM call timeout + retries (fail fast on proxy hiccups) |
| `LLM_REASONING_EFFORT` | `low` (empty = provider default) | Optional `low`/`medium`/`high`, passed to LiteLLM as `reasoning_effort` (with `drop_params`). Lower = faster answers on Gemini 3.x reasoning models. |

## Database (one DB `nimbus`, four schemas, DDL in `db/init/`)
Roles (created in `db/init/00_roles.sql`): `app` / password `app` (owner of schema `tools`,
SELECT on finance+trading+marketing); `agent_ro` / password `agent_ro` (SELECT on
finance+trading+marketing only, no access to `tools`). Every table and column gets `COMMENT ON`
(the UI renders these).

### finance
- `finance.entities` (entity_id text PK e.g. `NM-UK`, name text, country text, currency char(3))
- `finance.accounts` (account_code text PK e.g. `4100`, account_name text, account_type text
  check in (`revenue`,`expense`,`asset`,`liability`,`equity`), category text)
  - revenue categories include: `Trading commission`, `Spread revenue`, `Subscription fees`, `Interest income`
  - expense categories include: `Staff costs`, `Marketing`, `Technology`, `Office & admin`, `Payment processing`, `Professional fees`
- `finance.fx_rates` (rate_date date, currency char(3), usd_rate numeric(18,8)) PK (rate_date, currency); 1 unit of currency = usd_rate USD
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

### marketing (`db/init/25_marketing.sql`)
- `marketing.campaigns` (campaign_id text PK e.g. `CMP-001`, name text, entity_id → finance.entities,
  channel text check in (`search ads`,`social ads`,`video ads`,`app-store ads`,`affiliate network`), start_date date, end_date date)
  - one channel for one entity for one quarter, named like `NM-UK Q3 2026 - search ads`; from June 2026 NM-SG runs
    `Nimbus Go launch - <channel>` (filter with `name LIKE 'Nimbus Go%'`)
- `marketing.campaign_spend` (spend_id bigint PK, campaign_id → campaigns, spend_date date, spend_usd numeric(18,2) > 0,
  impressions bigint, clicks bigint): one row per ad invoice; bucket by `spend_date`
- `marketing.signups` (client_id text PK → trading.clients, campaign_id → campaigns, signup_date date): new clients
  credited to a campaign; about half of all new clients. `signup_date` = `trading.clients.signup_date`

Reconciliation property: every GL line on account `5200` (Performance marketing) is one `campaign_spend` row with
`spend_id` = `gl_entries.entry_id` and the same `amount_usd`, so campaign spend = GL 5200 to the cent, per entity and date.
The GL `Marketing` category also holds 5210 and 5220, which have no campaign.
Cost per sign-up = `SUM(spend_usd) / COUNT(signups)` for the same campaigns and period.

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
The registry is for finance and trading only; there are no marketing rows.

## Specialist interface (`src/devfest_agents/agents/`)
Each specialist module defines:

| name | type | example |
|---|---|---|
| `NAME` | str | `"finance_agent"` (function name the orchestrator calls) |
| `LABEL` | str | `"Finance agent"` |
| `DATASOURCE` | str | `"finance"` (schema it reads) |
| `DESCRIPTION` | str | what it answers; the orchestrator routes on it |
| `build(services, model)` | → `LlmAgent` | |

`my_agent/team.py`: `SPECIALISTS = [finance_agent, trading_agent, news_agent]` at the start of the workshop; participants
add `marketing_agent`. `my_agent/marketing_agent.py` starts as a stub: `DESCRIPTION = ""` and `build()` raises
`NotImplementedError` until exercise 2. `build_root_agent` builds and traces every entry, and `graph_agents()` builds the
`/api/graph` agents and datasources from it.

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
- Optional params with no default are passed as SQL NULL: write `(:entity_id IS NULL OR g.entity_id = :entity_id)`. Backend binds with explicit casts based on param type so NULL typing works.

Starter tools (the 6 seeded on first start): `finance_monthly_pnl`, `finance_revenue_breakdown`,
`finance_budget_vs_actual`, `trading_activity_summary`, `trading_top_instruments`, `trading_client_segment_performance`.

## Python function tools (`src/devfest_agents/tools/sql_query.py`)
Plain async functions passed in `LlmAgent(tools=[...])`. ADK wraps each in a `FunctionTool`: name, typed signature
and docstring become the declaration the LLM sees (the first docstring line is also its title in the catalogue and graph).

The marketing data team's queries live in `my_agent/marketing_queries.py`. Participants wrap them as
tools in `my_agent/marketing_agent.py` and don't write SQL. Dates are `YYYY-MM-DD` strings, both ends inclusive; entity ids
are `NM-UK`, `NM-SG`, `NM-AE`, `NM-INTL`; each returns what `run_sql` returns.
```python
async def fetch_campaign_performance(start_date: str, end_date: str, entity_id: str | None = None) -> dict
async def fetch_channel_summary(start_date: str, end_date: str, entity_id: str | None = None) -> dict
async def fetch_monthly_spend(start_date: str, end_date: str, entity_id: str | None = None,
                              channel: str | None = None) -> dict
async def fetch_entity_summary(start_date: str, end_date: str) -> dict
async def fetch_campaigns(entity_id: str | None = None, name_contains: str | None = None) -> dict
```

The queries call:
```python
await run_sql(schema: str, sql: str, **params) -> {"row_count": int, "truncated": bool, "rows": [dict, ...]} | {"error": "..."}
```
- `:name` placeholders, bound from `params`; a placeholder without a value is an error. No declared types: a bare NULL
  check needs a cast, e.g. `(:entity_id::text IS NULL OR c.entity_id = :entity_id)`.
- Same SQL guard as registry tools (single SELECT/WITH, only `schema`, schema-qualified tables), run as `agent_ro` in a
  read-only transaction, 5 s statement timeout, `TOOL_MAX_ROWS` cap.
- Guard and execution errors are returned as `{"error": ...}`, never raised.

## HTTP API (all JSON, base `/api`)

### Health / graph
- `GET /api/health` → `{"ok": true, "db": "ok"|"error", "llm_key": "configured"|"missing", "llm_mode": "proxy"|"direct", "model": "...", "router_model": "..."}  (never expose key or base URL)`
- `GET /api/graph` →
```json
{"agents": [
   {"id":"main_agent","label":"Main agent","role":"root","description":"...","model":"..."},
   {"id":"orchestrator","label":"Orchestrator","role":"router","parent":"main_agent",...},
   {"id":"finance_agent","label":"Finance agent","role":"specialist","parent":"orchestrator","datasource":"finance"},
   {"id":"trading_agent", ... "datasource":"trading"},
   {"id":"news_agent", ... "datasource":"internet"},
   {"id":"marketing_agent", ... "datasource":"marketing"}],
 "tools": [{"name":"finance_monthly_pnl","agent":"finance_agent","tool_type":"sql","title":"..."},
           {"name":"search_news","agent":"news_agent","tool_type":"mcp","title":"Search recent news for a query ..."},
           {"name":"channel_summary","agent":"marketing_agent","tool_type":"function","title":"Spend, clicks and sign-ups per ad channel for a date range."}],
 "datasources": [{"id":"finance","label":"finance schema"},{"id":"trading","label":"trading schema"},{"id":"internet","label":"Internet (RSS)"},{"id":"marketing","label":"marketing schema"}]}
```
Specialists, tools and datasources come from `SPECIALISTS`: `marketing_agent` and its tools appear only once it is
in the list. `tool_type`: `sql` | `factual` (registry) | `function` (Python tool) | `mcp` (news-mcp server). Tool titles: the registry `title`
for registry tools, the first docstring line for Python tools. The SPA draws the marketing agent dashed
("built in the workshop") until it appears here.

### Chat (SSE over POST)
`POST /api/chat` body `{"conversation_id": "uuid", "message": "text"}` → `text/event-stream`.
Each frame: `data: <json>\n\n`; keepalive comments `: ping\n\n`. Event JSON (`ts` = epoch ms on all):
```
{"type":"start","conversation_id":"..."}
{"type":"agent_start","agent":"orchestrator","invocation_id":"..."}
{"type":"agent_end","agent":"orchestrator","invocation_id":"...","ms":1234}
{"type":"tool_call","agent":"orchestrator","tool":"trading_agent","call_id":"c1","args":{"request":"..."},"kind":"agent"}   // kind: agent | sql | factual | function | mcp
{"type":"tool_result","agent":"orchestrator","tool":"trading_agent","call_id":"c1","ms":2100,"kind":"agent","ok":true,"row_count":null,"error":null,"preview":"first ~300 chars / rows"}
{"type":"answer_delta","text":"next chunk of the main agent's answer"}
{"type":"answer","text":"markdown","route":["main_agent","orchestrator","trading_agent","trading_top_instruments"],"elapsed_ms":5400}
{"type":"error","message":"..."}
```
A `tool_call` with `kind:"agent"` is a delegation edge from `agent` → `tool`. Others are leaf tool nodes under `agent`
(`function` = Python tool, labelled "Python" in the route panel).
Parallel fan-out = several `tool_call`s before their `tool_result`s.
`answer_delta` streams the main agent's answer as the model writes it (ADK SSE streaming); `answer` then carries the full text. Agents behind an `AgentTool` always run unary.
- `POST /api/chat/reset` body `{"conversation_id"}` → `{"ok":true}`
- `GET /api/chat/examples` → `[{"label":"Finance","prompt":"..."}, ...]` (the list is `EXAMPLES` in `api/routes_chat.py`;
  it includes Marketing and cross-agent prompts that need the marketing agent)

### Tools (registry: finance and trading only)
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
- `GET /api/schema` → `{"schemas":[{"name":"finance","comment":"..."},{"name":"trading",...},{"name":"marketing",...},{"name":"tools",...}]}`
- `GET /api/schema/{schema}` →
```json
{"name":"finance","comment":"...","tables":[{"name":"gl_entries","comment":"...","row_count":15000,
  "columns":[{"name":"entry_id","type":"bigint","nullable":false,"pk":true,"fk":null,"comment":"..."},
             {"name":"entity_id","type":"text","nullable":false,"pk":false,"fk":{"table":"entities","column":"entity_id"},"comment":"..."}]}]}
```
- `GET /api/schema/{schema}/{table}/sample?limit=5` → `{"columns":[...],"rows":[[...]]}` (limit ≤ 50)

Errors: non-2xx JSON `{"detail": "..."}`.

## Workshop checks (`src/devfest_agents/check.py`)
`make check-N` (N = 0..4) runs `python -m devfest_agents.check N` inside `nimbus-app`. It prints a ✓/✗ checklist for
exercise N, with a hint under every ✗, and exits non-zero if anything failed.

| N | checks |
|---|---|
| 0 | LLM key set; marketing data loaded |
| 1 | `my_agent/marketing_agent.py` has at least two `async def` tools; each has a docstring and type hints on every parameter; ADK can build a declaration for each; each returns rows for Q3 2026 |
| 2 | `DESCRIPTION` filled in; `build()` returns an `LlmAgent` named `marketing_agent` that uses `DESCRIPTION`, has an instruction and at least two tools |
| 3 | `marketing_agent` in `SPECIALISTS`; the orchestrator can call it; `my_agent/prompts/orchestrator.md` mentions it; one live practice question routes to it |
| 4 | three live practice questions (`spend-per-new-client`, `sg-marketing-booked`, `new-clients-september`) route correctly |

## Evals (`src/devfest_agents/evals.py`, `src/devfest_agents/judge.py`, `evals/practice.yaml`)
```
python -m devfest_agents.evals evals/practice.yaml [--only ID] [--parallel N] [--timeout S] > report.json
python -m devfest_agents.judge submissions.csv [--questions evals/final.yaml] [--engine podman]    # facilitators
```
- `make eval` runs the practice set (18 questions, every kind) and writes `evals/report.json`. `make eval Q=<id>` runs
  one question.
- `make submit` checks that `my_agent/` is committed and pushed, and prints the fork URL and commit to hand in.
- Questions run in parallel, 8 at a time by default (`--parallel`, or `make eval P=<n>`). Each runs as a fresh
  conversation. A question with no answer within 120 s (`--timeout`) scores 0, so one slow question can't hold up
  the run. Each specialist may call at most `MAX_TOOL_CALLS` (8) tools per request; further calls return an error
  telling it to answer with what it has.
- The results table goes to stderr: ✓/✗ for route and answer per question, a note of what was missing (or which agents
  were called, on a wrong route), a score per kind and the total. The JSON report goes to stdout.

Question format:
```yaml
- id: sg-spend-reconciles                    # unique; used by Q=<id>
  kind: multi-domain                         # lookup | analysis | multi-domain | routing | trap | adversarial
  question: Does NM-SG's ad campaign spend in September 2026 match the Performance marketing expense booked in the ledger for that month?
  agents: [marketing_agent, finance_agent]   # exactly the specialists the orchestrator should call; [] = none
  numbers: [13025.12]                        # optional; each must appear in the answer, within 1%
  words: []                                  # optional; each must appear, case-insensitive
  absent: []                                 # optional; none of these phrases may appear, case-insensitive
  judge: ""                                  # optional; one-line pass rule for an LLM judge
```
Each question scores 2 points:
- **route**: the set of agents the orchestrator called equals `agents`. Extra agents lose the point too.
- **answer**: every deterministic check passes, then the judge (if any) passes. Numbers like `$117,844.95`, `1.2M`,
  `58k` are parsed; a number matches within 1% of the expected value (relative, with a floor of 0.005 for tiny values).
  The judge runs only after the deterministic checks pass. It uses the router model and the participant's LLM key at
  temperature 0, and replies PASS or FAIL with a reason. A judge error costs the answer point, not the run.

Report: `{"score", "max_score", "results": [{id, kind, question, expected_agents, called_agents, route_point,
answer_point, missing, answer, error, elapsed_ms}]}`.

**The hidden set and the judge.** `evals/final.yaml` is gitignored and stays with the facilitators. The judge reads
a submissions CSV with `name` and `repo` columns, plus optional `commit` and timestamp columns; headers are matched
loosely, so a form export works as it is, and when a name appears twice the last row counts. For each submission it
checks out only `my_agent/` at the commit (the default branch's latest when none is given), runs the app image with
that folder mounted on the stack's network, asks every question through `POST /api/chat`, and grades outside the
participant's code. Each result keeps only `id, kind, route_point, answer_point, called_agents, error`. Results are
cached per commit in `platform/.judge/results/`; `platform/.judge/leaderboard.html` (self-refreshing) and
`leaderboard.json` rank by score, then earlier submission.

**Setup errors** stop the run with one ✗ line and exit code 1, instead of a stack trace: no LLM key; `marketing_agent`
in `SPECIALISTS` while its `build()` still raises `NotImplementedError`; the agents fail to build (e.g. a syntax
error); a missing question file or an unknown `--only` id. If `marketing_agent` is not
wired in yet, the run still happens, with a note that marketing questions will fail.

## SPA build
- `web/` is a Vite + React 18 + TS + Tailwind 4 app. `npm ci && npm run build` → `web/dist/`.
- Dev: `npm run dev` on :5173 proxies `/api` → `http://localhost:8080`.
- The app image copies `web/dist` → `/app/static`; FastAPI serves `/assets/*` and falls back to `index.html` for any non-`/api` path.

## LLM notes
- Any LiteLLM model string works (`gemini/...` direct, `openai/...` through an OpenAI-compatible proxy). Default: `gemini-3.7-flash`.
- Gemini 3.x spends **reasoning tokens** out of the completion budget: don't set a small `max_tokens` (a tiny cap returns empty answers). `LLM_REASONING_EFFORT=low` (the default) keeps cross-agent answers around 20-35 s.
- `.env` values may be quoted (`KEY="value"`); Docker Compose strips the quotes. `.env` is gitignored and excluded from images; `.env.example` holds placeholders only.
