# Demo script: talk track (about 15 minutes)

**Setup before going on stage:** `make up` (or `make podman-up`) has finished. Open
http://localhost:8080 on the Chat page, with http://localhost:8000 (ADK dev UI) in a second tab.
Run one warm-up question so models and connections are hot.

> Say early and often: **all company data is synthetic.** Nimbus Markets is a fictional broker, and
> prices, clients and ledgers are generated. Only the headlines are real (public RSS).

## The data and its planted storylines

The committed CSVs cover **June 2025 to 5 Nov 2026**, so November is month-to-date. They were
generated on 2026-11-06. The storylines are placed relative to the last month, so they move with
`make data`. The dates below are for the committed data.

| # | Storyline | Where it shows |
|---|---|---|
| 1 | **Crypto spike, Oct 2026.** A synthetic BTC/ETH rally (about +30%) and about 3x the usual crypto trades. Trading commission is about $306k vs about $169k in September, and revenue beats budget by about 50%. **Bitcoin** is the top commission instrument (about 47% of commission). | `trading_top_instruments`, `trading_activity_summary(by_asset_class)`, `finance_budget_vs_actual(2026-10)` |
| 2 | **Revenue miss, Aug 2026.** Trading volumes in every asset class fall to about 55% of normal. Revenue is about $209k vs about $390k budget (-46%), commission and spread are both about -50%, and the group makes an **operating loss** (about -$54k). | `finance_budget_vs_actual(2026-08)`, `finance_monthly_pnl`, `trading_activity_summary` |
| 3 | **Marketing overrun at NM-SG, Jun 2026 onwards.** The Nimbus Go regional campaign runs 35-60% over the Marketing budget, and the overrun grows each month. Other entities stay within about ±15% (volume-linked costs dip in August). | `finance_budget_vs_actual(by_entity=true)` or `entity_id=NM-SG` |
| 4 | **Commission reconciles.** For every month and entity, GL "Trading commission" equals the trading desk's `SUM(commission_usd)` within cents. Q3 2026: GL $441,649.80 vs desk $441,649.73. | `finance_revenue_breakdown(category=Trading commission)` + `trading_activity_summary` |

Other facts that are handy on stage:

- 4 entities (NM-UK GBP, NM-SG SGD, NM-AE AED, NM-INTL USD), 600 clients, 16 instruments, about 20k
  trades and about 16k GL lines.
- VIP clients (about 8% of clients) generate about 60% of commission.
- Clients lose money on aggregate (client PnL is negative over the period), though some months they
  win.

## 1. The architecture (2 min)

Open the Overview page and walk the diagram:

> "One main agent with a persona. It delegates to an orchestrator, whose only job is routing. Below it
> are three specialists: finance and trading, whose tools are **rows in Postgres**, and news, which
> talks to our own **MCP server** that polls RSS feeds. In ADK, every arrow in this diagram is an
> `AgentTool`."

## 2. One question per agent (3 min)

Ask these one at a time and point at the route panel each time.

| Ask | Expect |
|---|---|
| *"What was our operating profit in each month of Q3 2026?"* | `finance_agent → finance_monthly_pnl`. August is a loss. |
| *"What were the most traded instruments last month?"* | `trading_agent → trading_top_instruments`. Bitcoin is on top. |
| *"What's moving the crypto market today?"* | `news_agent → latest_headlines(crypto)`. These are real headlines. |

Talking point: *"There's no classifier model. The orchestrator is just choosing which function to
call. Its instruction is rebuilt every turn with the live list of tools, so routing knows what each
agent can do right now."*

## 3. Cross-agent questions (6 min)

**a) Reconciliation, parallel fan-out (storyline 4)**

> *"Does the commission revenue we booked in Q3 2026 match what the trading desk earned?"*

- Route: finance **and** trading light up **at the same time**.
- Finance runs `finance_revenue_breakdown` (Trading commission) and trading runs
  `trading_activity_summary`.
- Answer: they match to within cents (FX rounding).
- Point at the two simultaneous `tool_call` edges: *"this is ADK running both AgentTools
  concurrently."*

**b) Budget miss explained, all three agents (storyline 2)**

> *"Why did we miss revenue budget in August 2026?"*

1. Finance: `finance_budget_vs_actual(2026-08)`. Commission and spread are about -50%, and
   costs are on budget.
2. Trading: `trading_activity_summary`. Trades fell from about 1,300 to about 700 and volume halved.
3. News: market context.

Talking point: *"Notice the orchestrator rewrote the question for each specialist with explicit
dates. Specialists don't see the chat, so every sub-question is self-contained."*

**c) Revenue driver plus context, sequential (storyline 1)**

> *"Which instrument drove the most commission last month, and what's in the news about it?"*

- First trading runs `trading_top_instruments(metric=commission)` and finds **Bitcoin**.
- **Then** news runs `search_news("Bitcoin")`.
- Point out that the second call could only be made after the first returned.

**d) Segment profitability (finance + trading)**

> *"Are VIP clients worth it? Compare their Q3 2026 commission with our total operating profit."*

- Trading: `trading_client_segment_performance`. VIP commission is about $270k, about 61% of the
  total.
- Finance: `finance_monthly_pnl` for Q3.

**e) Optional: cost overrun (storyline 3)**

> *"Which costs overran budget in September 2026, and in which entity?"*

- `finance_budget_vs_actual(by_entity=true)` shows **NM-SG Marketing about +55%**.

## 4. Teach a new skill live (3 min)

Follow WORKSHOP.md Step 2 (`finance_fx_rates`) or Step 4 (`kpi_definitions`):

1. **Tools → New**: paste the SQL and **Test**. Show the "what the LLM sees" declaration.
2. **Save**, then ask *"What was the average GBP to USD rate in Q3 2026?"*
3. The new tool node appears in the route **without a restart**: the toolset fingerprint changed, so
   the agent rebuilt its tools on this question.

## 5. Wrap-up (1 min)

- Agents as tools: `AgentTool` gives you hierarchy, parallelism and sequencing from plain function
  calling.
- Tools as data: a registry plus a factory plus a hot-reloading `BaseToolset` lets analysts ship
  agent skills without code.
- Safety comes from the DB role, the SQL guard, read-only transactions and a delegation cap.
- MCP brings in outside context (news) behind the same tool interface.
- Repo: one `make up`, 100% synthetic data, runs on Docker or Podman.

## Troubleshooting on stage

| Symptom | Fix |
|---|---|
| News answers "live news unavailable" | The venue Wi-Fi is down. The news server fails soft, so carry on. |
| "LLM key: missing" on Overview | `.env` has no key. Fix it and restart with `make up`. |
| Old data or tools | `make reset` (or `make podman-reset`) reloads the CSVs. `make seed-tools` re-applies the starter YAML. |
| Port 5432 busy | Set `POSTGRES_PORT=5433` in `.env`. |
