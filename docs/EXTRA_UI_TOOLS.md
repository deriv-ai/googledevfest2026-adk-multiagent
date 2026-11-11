# Extra: teach finance and trading new skills from the UI

> **The main workshop is [WORKSHOP.md](../WORKSHOP.md)**, where you build the marketing agent. This
> page is an optional side exercise for when you finish early, or want better finance and trading
> tools for the competition in [exercise 5](../exercises/5-evals.md).

**Time:** about 45 minutes. **You need:** the stack running (`make up`, see
[WORKSHOP.md](../WORKSHOP.md)) and a browser at http://localhost:8080.

The finance and trading agents get their tools from a registry in Postgres, and the UI has an editor
for it. The marketing agent is different: its tools are Python functions, so this page doesn't apply
to it.

The starter registry has 3 finance and 3 trading SQL tools. It deliberately has **no FX-rate tool, no
client risk-level tool and no curated definitions**, and you will add all three. You won't touch any
Python. You write a tool in the UI, test it, save it, and the agents pick it up on the next question.

> All data is synthetic: Nimbus Markets is a fictional broker and every number is generated.

---

## Step 0: see the gap

1. Open **Chat** and ask: *"What was the average GBP to USD rate in Q3 2026?"*
2. Watch the **Agent Route** panel. The orchestrator routes to `finance_agent`, which has no tool
   for FX rates. A well-behaved agent says it can't answer rather than inventing a number. That is the
   gap you are about to close.

## Step 1: explore the schema

Open **Data Schema → finance**.

- Click `fx_rates`. Read the table and column descriptions: these are the `COMMENT ON` texts from the
  database, so they always match what is really there. Note that **1 unit of currency = `usd_rate`
  USD**, there is one row per calendar day, and the currencies are AED, EUR, GBP, SGD and USD.
- Look at the 5 sample rows.
- Switch to **trading → clients** and note `risk_level` (`low|medium|high`) and `segment`.
- Glance at `trades`: `commission_usd` is Nimbus revenue, `pnl_usd` is the *client's* result, and you
  should bucket by `close_time`.

Tips for writing tools that LLMs use well:

- **Schema-qualify every table** (`finance.fx_rates`). The guard rejects unqualified names and other
  agents' schemas.
- Use **`:param` placeholders**. `::date` casts are fine and are not placeholders.
- Make optional filters NULL-safe: `(:currency IS NULL OR r.currency = :currency)`.
- **Name the units in the column aliases** (`avg_usd_rate`, `commission_usd`) and in the description.
- The **description is the prompt**: say what it returns, when to use it, and how it combines with
  other tools.

## Step 2: an FX tool for the finance agent

**Tools → New tool**, type **SQL**.

| Field | Value |
|---|---|
| name | `finance_fx_rates` |
| agent | `finance` |
| title | `Monthly FX rates to USD` |

**Description:**

> Monthly FX statistics from finance.fx_rates for AED, EUR, GBP and SGD. One row per month and
> currency, with avg_usd_rate, min_usd_rate, max_usd_rate and month_end_usd_rate, where 1 unit of
> currency = rate USD. Use it for "what was the average GBP rate in Q3?", for converting a USD figure
> into local currency (divide by the rate), or to explain FX effects on an entity's USD results
> (NM-UK books in GBP, NM-SG in SGD, NM-AE in AED).

**SQL:**

```sql
SELECT date_trunc('month', r.rate_date)::date AS month,
       r.currency,
       ROUND(AVG(r.usd_rate), 6) AS avg_usd_rate,
       MIN(r.usd_rate) AS min_usd_rate,
       MAX(r.usd_rate) AS max_usd_rate,
       (ARRAY_AGG(r.usd_rate ORDER BY r.rate_date DESC))[1] AS month_end_usd_rate
FROM finance.fx_rates r
WHERE r.rate_date BETWEEN :start_date AND :end_date
  AND (:currency IS NULL OR r.currency = :currency)
  AND r.currency <> 'USD'
GROUP BY 1, 2
ORDER BY 2, 1
```

The params editor fills itself from the placeholders. Complete it:

| name | type | required | extra |
|---|---|---|---|
| `start_date` | date | yes | example `2026-07-01` |
| `end_date` | date | yes | example `2026-09-30` |
| `currency` | string | no | enum `AED, EUR, GBP, SGD` |

Click **Test**. You should see 12 rows (4 currencies × 3 months). Look at the **"what the LLM sees"**
panel: this is the exact function declaration Gemini receives, generated from your row. Click
**Save**.

Now go back to Chat and ask the Step 0 question again. The route shows
`finance_agent → finance_fx_rates`, and you never restarted anything. Ask
*"What can the finance agent do now?"* as well: the orchestrator's live catalogue already lists the
new tool.

## Step 3: a client risk tool for the trading agent

New tool, type **SQL**, agent `trading`:

| Field | Value |
|---|---|
| name | `trading_client_risk_mix` |
| title | `Commission and client PnL by risk level` |

**Description:**

> Breaks down closed-trade activity for a date range by the clients' onboarding risk_level (high,
> medium, low): active_clients, trades, notional_usd, commission_usd, commission_share_pct,
> client_pnl_usd (clients' result, negative = they lost) and avg_trade_notional_usd. Optional segment
> filter (retail/pro/vip). Use it for "how dependent are we on high-risk clients?" or "do high-risk VIPs
> trade bigger?".

**SQL:**

```sql
SELECT c.risk_level,
       COUNT(DISTINCT c.client_id) AS active_clients,
       COUNT(*) AS trades,
       ROUND(SUM(t.notional_usd), 2) AS notional_usd,
       ROUND(SUM(t.commission_usd), 2) AS commission_usd,
       ROUND(100 * SUM(t.commission_usd) / SUM(SUM(t.commission_usd)) OVER (), 1) AS commission_share_pct,
       ROUND(SUM(t.pnl_usd), 2) AS client_pnl_usd,
       ROUND(AVG(t.notional_usd), 2) AS avg_trade_notional_usd
FROM trading.trades t
JOIN trading.clients c ON c.client_id = t.client_id
WHERE t.status = 'closed'
  AND t.close_time >= :start_date::date
  AND t.close_time <  :end_date::date + 1
  AND (:segment IS NULL OR c.segment = :segment)
GROUP BY c.risk_level
ORDER BY CASE c.risk_level WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END
```

Params:

| name | type | required | extra |
|---|---|---|---|
| `start_date` | date | yes | example `2026-07-01` |
| `end_date` | date | yes | example `2026-09-30` |
| `segment` | string | no | enum `retail, pro, vip` |

Test (3 rows), save, then ask: *"What share of Q3 commission came from high-risk VIP clients?"*

**Try breaking it on purpose.** Each of these makes the test fail with a clear error, which is the
SQL guard and param validation doing their job:

- change `trading.trades` to `finance.gl_entries`: another agent's schema;
- add `; DELETE FROM trading.trades`: multiple statements, not a SELECT;
- rename `:segment` in the SQL but not in the params: placeholder/param mismatch.

## Step 4: a factual tool (curated knowledge, no SQL)

Some questions don't need a query at all. They need **the company's definition**. New tool, type
**Factual**, agent `finance`:

| Field | Value |
|---|---|
| name | `kpi_definitions` |
| title | `How Nimbus defines its KPIs` |
| source | `Nimbus Finance Handbook, section 2 (fictional)` |

**Description:**

> Official Nimbus Markets definitions of financial KPIs: net revenue, operating profit, margin,
> trading volume, active client. Use it when the user asks how a metric is defined or calculated, or
> before comparing numbers that depend on a definition.

**Answer (markdown):**

```markdown
**Nimbus Markets KPI definitions** (fictional)

- **Net revenue**: trading commission + spread revenue + subscription fees + interest income,
  in USD, as booked in the general ledger. Client PnL is *not* revenue.
- **Operating profit**: net revenue minus operating expenses (staff, marketing, technology,
  office & admin, payment processing, professional fees).
- **Operating margin**: operating profit / net revenue x 100.
- **Trading volume**: sum of notional (USD) of trades closed in the period.
- **Active client**: a client with at least one closed trade in the period.
- **Commission reconciliation**: GL account 4100 must match trading-desk commission per month and
  entity within USD 1.00 (FX rounding).
```

Test: there are no params, and the declaration panel shows a function **with no arguments**. Save,
then ask: *"How do we define net revenue, and what was it in September 2026?"* The route shows the
finance agent calling `kpi_definitions` **and** `finance_monthly_pnl` (or
`finance_revenue_breakdown`), and the answer uses your definition.

## Step 5: cross-agent questions

Now use everything together. Watch the route panel for parallel branches.

- *"Did GBP strength or weakness affect NM-UK's USD revenue in Q3 2026?"* (finance: FX + P&L)
- *"Which risk level earned us the most commission last month, and how did that month's revenue
  compare with budget?"* (trading + finance)
- *"Why did we miss revenue budget in August 2026?"* (finance → trading)

## Bonus challenges

- Disable a tool (toggle on the Tools page) and ask a question that needs it. What does the
  orchestrator do?
- Write `trading_instrument_returns`, a monthly % return per instrument from `trading.daily_prices`,
  then ask whether the October crypto rally explains the commission spike.
- Write `finance_expense_trend` for one category across entities, and find the entity whose Marketing
  spend keeps overrunning.
- Write a finance tool for a **single GL account**, for example 5200 Performance marketing, per month
  and entity. The starter finance tools only report by category, and the Marketing category also holds
  5210 and 5220. With it, finance can reconcile the marketing agent's campaign spend against the ledger
  to the cent. This is a useful idea for the competition.
- Open the ADK dev UI (http://localhost:8000) and compare its event view with the app's route panel.
