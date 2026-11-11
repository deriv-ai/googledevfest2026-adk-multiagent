# Demo script: facilitator talk track (about 20 minutes)

**Setup before going on stage:** `make up` (or `make podman-up`) has finished. Open
http://localhost:8080 on the Chat page, with http://localhost:8000 (ADK dev UI) in a second tab.
Run one warm-up question so the model connection is hot. Have a second checkout (or branch) ready
where `marketing_agent` is already in `SPECIALISTS`, for sections 4 and 5.

> Say early and often: **all company data is synthetic.** Nimbus Markets is a fictional broker, and
> prices, clients, ledgers and campaigns are generated.

## The data and its planted storylines

The committed CSVs cover **June 2025 to 5 Nov 2026**, so November is month-to-date. They were
generated on 2026-11-06. The storylines are placed relative to the last month, so they move with
`make data`. The dates below are for the committed data.

| # | Storyline | Where it shows |
|---|---|---|
| 1 | **Crypto spike, Oct 2026.** A synthetic BTC/ETH rally (about +30%) and about 3x the usual crypto trades. Trading commission is about $306k vs about $169k in September, and revenue beats budget by about 50%. **Bitcoin** is the top commission instrument (about 47% of commission). | `trading_top_instruments`, `trading_activity_summary(by_asset_class)`, `finance_budget_vs_actual(2026-10)` |
| 2 | **Revenue miss, Aug 2026.** Trading volumes in every asset class fall to about 55% of normal. Revenue is about $209k vs about $390k budget (-46%), commission and spread are both about -50%, and the group makes an **operating loss** (about -$54k). | `finance_budget_vs_actual(2026-08)`, `finance_monthly_pnl`, `trading_activity_summary` |
| 3 | **Marketing overrun at NM-SG, Jun 2026 onwards.** NM-SG's Marketing costs run 34-57% over budget every month. October: $20,803.80 actual vs $13,262.16 budget (+$7,541.64). Other entities stay within about ±15% (volume-linked costs dip in August). | `finance_budget_vs_actual(by_entity=true)` or `entity_id=NM-SG` |
| 4 | **Commission reconciles.** For every month and entity, GL "Trading commission" equals the trading desk's `SUM(commission_usd)` within cents. Q3 2026: GL $441,649.80 vs desk $441,649.73. | `finance_revenue_breakdown(category=Trading commission)` + `trading_activity_summary` |
| 5 | **The Nimbus Go campaign, Jun 2026 onwards.** Storyline 3 seen from the marketing side. NM-SG's "Nimbus Go launch" campaigns spent $60,335.35 in Jun-Oct 2026 vs $34,171.37 for NM-SG's campaigns in Jan-May, but brought in 18 sign-ups vs 16. Cost per sign-up rose from about $2,136 to about $3,352. | marketing agent: campaign or channel tools, `entity_id=NM-SG` |

**Campaign spend ↔ ledger.** Every GL line on account 5200 (Performance marketing) is one
`marketing.campaign_spend` row with the same id and USD amount, so campaign spend equals GL 5200 to the
cent. The GL **Marketing** category is wider: it adds 5210 (Brand and events) and 5220
(Introducing-partner commissions). In September 2026 NM-SG's campaigns spent $13,025.12, which is its
5200 total, while its whole Marketing category was $20,353.74. The starter finance tools only report
by category, so finance gives you the $20,353.74, not the 5200 figure.

Other facts that are handy on stage:

- 4 entities (NM-UK GBP, NM-SG SGD, NM-AE AED, NM-INTL USD), 600 clients, 16 instruments, about 20k
  trades, about 16k GL lines, 117 campaigns, 276 ad invoices and 195 campaign sign-ups.
- VIP clients (about 8% of clients) generate about 60% of commission.
- Clients lose money on aggregate (client PnL is negative over the period), though some months they
  win.
- Q3 2026: campaigns spent $117,844.95 and brought in 58 of the 113 new clients. App-store ads had the
  lowest cost per sign-up ($1,635.34). NM-INTL's campaigns brought in the most sign-ups (29).

## 1. The architecture (2 min)

Open the Overview page and walk the diagram:

> "One main agent with a persona. It delegates to an orchestrator, whose only job is routing. Below it
> are the specialists. Finance and trading get their tools from **rows in Postgres**. The dashed one,
> marketing, doesn't exist yet: that's what you build today. In ADK, every arrow in this diagram is an
> `AgentTool`."

Point at the `marketing` tab on the Schema page: the data is already there, no agent reads it yet.

## 2. One question per agent, and the gap (3 min)

Ask these one at a time and point at the route panel each time.

| Ask | Expect |
|---|---|
| *"What was our operating profit in each month of Q3 2026?"* | `finance_agent → finance_monthly_pnl`. August is a loss. |
| *"What were the most traded instruments last month?"* | `trading_agent → trading_top_instruments`. Bitcoin is on top. |
| *"How much did our ad campaigns spend in Q3 2026?"* | No marketing agent yet. The orchestrator either says no specialist covers it, or asks finance, which only knows marketing costs as booked by category. Neither gives the campaign figure. |

Talking point: *"There's no classifier model. The orchestrator is just choosing which function to
call. Its instruction is rebuilt every turn with the live list of tools, so routing knows what each
agent can do right now. Today you give it one more function to call."*

## 3. Cross-agent questions with what exists (4 min)

**a) Reconciliation, parallel fan-out (storyline 4)**

> *"Does the commission revenue we booked in Q3 2026 match what the trading desk earned?"*

- Route: finance **and** trading light up **at the same time**.
- Finance runs `finance_revenue_breakdown` (Trading commission) and trading runs
  `trading_activity_summary`.
- Answer: they match to within cents (FX rounding).
- Point at the two simultaneous `tool_call` edges: *"this is ADK running both AgentTools
  concurrently."*

**b) Budget miss explained (storyline 2)**

> *"Why did we miss revenue budget in August 2026?"*

1. Finance: `finance_budget_vs_actual(2026-08)`. Commission and spread are about -50%, and
   costs are on budget.
2. Trading: `trading_activity_summary`. Trades fell from about 1,300 to about 700 and volume halved.

Talking point: *"Notice the orchestrator rewrote the question for each specialist with explicit
dates. Specialists don't see the chat, so every sub-question is self-contained."*

**c) Sequential**

> *"Which entity earned the most commission last quarter, and did it hit its revenue budget?"*

- First trading finds the entity, **then** finance checks that entity's budget.
- Point out that the second call could only be made after the first returned.

## 4. Add the marketing agent (3 min)

Switch to the checkout where `marketing_agent` is in `SPECIALISTS`, or make the change live. Show:

1. `marketing_agent.py`: `NAME`, `LABEL`, `DATASOURCE`, `DESCRIPTION` and `build()`. The tools are
   plain async functions. The docstring is the prompt: ADK turns the signature and docstring into the
   declaration the LLM sees.
2. Each tool calls `run_sql("marketing", sql, ...)`, which gives it the same guard, read-only role,
   timeout and row cap as the registry tools.
3. One line in `agents/__init__.py` adds it to `SPECIALISTS`. `./src` is mounted and the app reloads,
   so there is no rebuild.
4. Refresh the Overview page: the dashed marketing node turns solid, because it now appears in
   `/api/graph`.

The full walkthrough for participants is [GUIDE.md](../GUIDE.md).

## 5. Marketing and cross-domain questions (4 min)

**a) Marketing alone**

> *"Which ad channel had the lowest cost per sign-up in Q3 2026, and what was it?"*

- `marketing_agent` with a Python tool, labelled "Python" in the route panel.
- Answer: app-store ads, $1,635.34 per sign-up.

**b) Campaign spend vs the ledger, parallel (the 5200 reconciliation)**

> *"Does NM-SG's ad campaign spend in September 2026 match the Performance marketing expense booked
> in the ledger for that month?"*

- Marketing and finance light up together.
- Marketing: $13,025.12. Finance with the starter tools: the whole Marketing category, $20,353.74.
- Talking point: *"They don't match, and that's correct: the category also holds brand and partner
  costs. To answer this properly, finance needs a tool for a single GL account. That's a good idea for
  the competition."*

**c) Marketing + trading**

> *"How many new clients signed up in Q3 2026 in total, and how many of them were brought in by ad
> campaigns?"*

- Trading: 113 new clients. Marketing: 58 from campaigns.
- Routing rule on screen: *sign-ups credited to a campaign are marketing, all new clients are
  trading.*

**d) Was Nimbus Go worth it? (storylines 3 and 5)**

> *"Was the Nimbus Go campaign worth the money?"*

- Marketing: $60,335.35 spent in Jun-Oct 2026 for 18 sign-ups, about $3,352 each, vs about $2,136
  per sign-up for NM-SG's earlier campaigns.
- Finance: NM-SG Marketing in October 2026 was $20,803.80 against a $13,262.16 budget.
- The answer should say spend went up much faster than sign-ups.

**e) Routing trap**

> *"What was NM-SG's total Marketing expense booked in the ledger in September 2026?"*

- Finance only ($20,353.74). If marketing lights up too, the description or routing rules need work.

## 6. Scoring (1 min)

Run `make eval` (or `make eval Q=sg-spend-reconciles` for one question) and open
`evals/report.json`.

- Each question is worth 2 points: **route** (the orchestrator called exactly the expected agents) and
  **answer** (every expected number within 1%, every expected word).
- The practice set is `evals/practice.yaml`. A leaderboard on a different question set is coming
  later, so tune for this kind of question, not these exact ones.

## 7. Wrap-up (1 min)

- Agents as tools: `AgentTool` gives you hierarchy, parallelism and sequencing from plain function
  calling.
- Two ways to give an agent skills: tools as data (a registry plus a hot-reloading `BaseToolset`) and
  tools as Python functions (signature + docstring). Both share one SQL guard and one read-only role.
- A new specialist is one module and one line in `SPECIALISTS`. The orchestrator, tracing and UI pick
  it up from there.
- Repo: one `make up`, 100% synthetic data, runs on Docker or Podman.

## Troubleshooting on stage

| Symptom | Fix |
|---|---|
| "LLM key: missing" on Overview | `.env` has no key. Fix it and restart with `make up`. |
| Marketing node still dashed | `marketing_agent` is not in `SPECIALISTS`, or the app has not reloaded yet. Check `make logs`. |
| Old data or tools | `make reset` (or `make podman-reset`) reloads the CSVs. `make seed-tools` re-applies the starter YAML. |
| Port 5432 busy | Set `POSTGRES_PORT=5433` in `.env`. |
