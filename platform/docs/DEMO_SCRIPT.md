# Demo script: facilitator talk track

The sections follow the workshop. Each one introduces an exercise from
[the README](../../README.md); participants then do it and run its `make check-N`.

The whole session is 60 minutes, setup and competition included, so keep each introduction to
about a minute. The demos in sections 2, 3 and 7 are optional: use them only if the room is ahead.

| Time | Participants | You |
|---|---|---|
| 0:00 | Clone, add key, `make up`, read the task | Present the task (section 1). Walk the room for setup problems. |
| 0:10 | Exercise 0 | Show the refusal and the `## Not covered yet` section. |
| 0:14 | Exercise 1 | Introduce tools and docstrings (section 4). |
| 0:23 | Exercise 2 | Description vs instruction (section 5). |
| 0:29 | Exercise 3 | Agents as tools (section 6). |
| 0:35 | Exercise 4 | Parallel, sequential, tie-breaks (section 7). |
| 0:42 | Exercise 5: score, fix one failure, rerun | Show one improvement cycle (section 8). Put the Drive folder link on screen. |
| 0:45 | | Start judging: download the Drive folder and run `make -C platform judge` on it. Repeat every few minutes as uploads arrive. |
| 0:52 | `make submit NAME=...`, upload the zip | Stop accepting uploads at 0:54. |
| 0:54 | | Final download and judge run, leaderboard on screen, the final question (section 9). |

Which improvements separate a finished workshop from full marks, and what the reference
solutions score, is in [CHALLENGES.md](CHALLENGES.md).

**Setup before going on stage:** `make up` has finished. Open http://localhost:8080 on the Chat
page, with http://localhost:8000 (ADK dev UI) in a second tab. Run one warm-up question so the model
connection is hot. Have a second checkout (or branch) ready with exercises 1 to 4 done, for sections
4 to 8. Have a Google Drive folder that anyone with the link can upload to, and the judge set up as in
[the platform README](../README.md).

> Say early and often: **all company data is synthetic.** Nimbus Markets is a fictional broker, and
> prices, clients, ledgers and campaigns are generated.

## The data and its planted storylines

The committed CSVs cover **June 2025 to 5 Nov 2026**, so November is month-to-date. They were
generated on 2026-11-06. The storylines are placed relative to the last month, so they move with
`make -C platform data`. The dates below are for the committed data.

| # | Storyline | Where it shows |
|---|---|---|
| 1 | **Crypto spike, Oct 2026.** A synthetic BTC/ETH rally (about +30%) and about 3x the usual crypto trades. Trading commission is about $306k vs about $169k in September, and revenue beats budget by more than 50%. **Bitcoin** is the top commission instrument (about 47% of commission). | `trading_top_instruments`, `trading_activity_summary(by_asset_class)`, `finance_budget_vs_actual(2026-10)` |
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
- VIP clients (about 8% of clients) generate about 65% of commission.
- Clients lose money on aggregate (client PnL is negative over the period), though some months they
  win.
- Q3 2026: campaigns spent $117,844.95 and brought in 58 of the 113 new clients. App-store ads had the
  lowest cost per sign-up ($1,635.34). NM-INTL's campaigns brought in the most sign-ups (29).

## 1. The task and the architecture (exercise 0, 3 min)

Present the task from [the README](../../README.md): the assistant answers finance, trading and
news questions, but not marketing ones. NM-SG launched the Nimbus Go app in June 2026 with ad
campaigns. Participants add a marketing agent, and the final question is whether Nimbus Go was
worth the money.

Open the Overview page and walk the diagram:

> "One main agent with a persona. It delegates to an orchestrator, whose only job is routing. Below it
> are the specialists. Finance and trading get their tools from **rows in Postgres**. News gets its
> tools from an **MCP server** that reads live headlines. The dashed one,
> marketing, doesn't exist yet: that's what you build today. In ADK, every arrow in this diagram is an
> `AgentTool`."

Then:

1. Ask *"How did the Nimbus Go campaigns do?"* The orchestrator has nobody to send it to.
2. Point at the `marketing` tab on the Schema page: the data is already there, no agent reads it yet.
3. Open `my_agent/marketing_queries.py`: the tested queries they're
   given. *"Nobody writes SQL today. Your job is to make these usable by a model."*

Participants run `make check-0` (LLM key and marketing data). Tell them `make eval` already works and
the score starts low.

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

## 4. Creating tools (exercise 1, 3 min)

Switch to the finished checkout. Show `my_agent/marketing_agent.py` next to `marketing_queries.py`:

1. A tool is a plain async function that calls one of the marketing queries, for example
   `queries.fetch_channel_summary(...)`.
2. ADK turns the name, the type hints and the docstring into the declaration the model sees. The
   model never sees the body. *"The docstring is the prompt."*
3. A good docstring says what comes back (columns and units), when to use it, and the format of each
   argument (`YYYY-MM-DD`, entity ids).
4. The queries run through `run_sql`, with the same SQL guard, read-only role, timeout and row cap as
   the registry tools.

Participants write two tools (campaigns and channels) and run `make check-1`: tools found,
docstrings, type hints, ADK can declare them, and they return data.

## 5. Hire the agent (exercise 2, 2 min)

Show `DESCRIPTION` and `build()`:

- `description` faces outward: the orchestrator reads it to decide whether to send work.
- `instruction` faces inward: rules for the agent. It comes from `my_agent/prompts/marketing_agent.md`.
- `build()` returns an `LlmAgent` with the tools from section 4.

Participants run `make check-2`.

## 6. Adding an agent to the orchestrator (exercise 3, 2 min)

1. One line in `my_agent/team.py` adds `marketing_agent` to `SPECIALISTS`. `./src` is mounted and
   the app reloads, so there is no rebuild.
2. One line in `my_agent/prompts/orchestrator.md` under `## Specialists` says what marketing covers.
3. Refresh the Overview page: the dashed marketing node turns solid, because it now appears in
   `/api/graph`.
4. Ask *"How many new clients did our ad campaigns bring in during October 2026?"* The route shows
   `marketing_agent` with a tool labelled "Python". Answer: 23.

Participants run `make check-3`. It asks one live question, so it takes a few seconds.

## 7. Routing across agents (exercise 4, 4 min)

Words mean different things to different teams. Show the tie-break rules participants add under
`## Routing rules` in `my_agent/prompts/orchestrator.md`: *spend per campaign or channel is marketing, marketing
costs as booked in the ledger are finance; sign-ups credited to a campaign are marketing, all new
clients are trading.*

**a) Marketing alone**

> *"Which ad channel had the lowest cost per sign-up in Q3 2026, and what was it?"*

- `marketing_agent` only. Answer: app-store ads, $1,635.34 per sign-up.

**b) Marketing + trading, parallel**

> *"What did each new client cost us in Q3 2026, counting every client who signed up?"*

- Marketing: $117,844.95 of campaign spend. Trading: 113 new clients.
- About $1,042.88 per new client. Only 58 of the 113 came from a campaign, which is why trading is
  needed.

**c) Campaign spend vs the ledger (the 5200 reconciliation)**

> *"Does NM-SG's ad campaign spend in September 2026 match the Performance marketing expense booked
> in the ledger for that month?"*

- Marketing and finance light up together.
- Marketing: $13,025.12. Finance, with `finance_expense_by_account`: account 5200 Performance
  marketing, $13,025.12, a match to the cent.
- Talking point: *"They match because every campaign invoice is booked on account 5200. The whole
  Marketing category is bigger, $20,353.74, because it also holds brand and partner costs. Same
  word, different numbers: that's what routing rules are for."*

**d) Was Nimbus Go worth it? (storylines 3 and 5)**

> *"Was the Nimbus Go campaign worth the money?"*

- Marketing: $64,226.88 spent from 15 June to 5 November 2026 for 18 sign-ups, $3,568.16 each,
  against $2,031.81 for all campaigns in Q3 2026.
- Finance: NM-SG's Marketing costs in Q3 2026 were $55,738.66, 43.2% over a $38,918.60 budget.
- Trading: NM-SG earned $87,235.84 in commission in Q3 2026, from all its clients.
- Talking point: *"The data can't settle it. Commission is per entity, not per client, so nothing
  shows what the 18 new clients trade. A good answer says that."* This is the closing question of
  the session; exercise 5's "The final question" has the full answer.

**e) Routing traps**

> *"What was NM-SG's total Marketing expense booked in the ledger in September 2026?"*

- Finance only ($20,353.74).

> *"How many new clients signed up in September 2026, whether or not a campaign brought them in?"*

- Trading only (38).

If marketing lights up on either, the description or routing rules need work.

Participants run `make check-4`. It asks three live questions and checks the agents, the answer,
and the order: parallel means both calls before either answer; sequential means the second call
comes after the first answer and uses what it found.

## 8. Evaluating agents, and the competition (exercise 5, 3 min)

Run `make eval` (or `make eval Q=worst-channel-chain` for one question). Show the table on screen:

- Each question is worth 2 points: **route** (the orchestrator called exactly the expected agents,
  no more, no fewer) and **answer** (every check passes).
- Answer checks: expected numbers within 1%, expected words, phrases that must not appear, and for
  some questions a one-line rule checked by an LLM judge.
- Six kinds: lookup, analysis, multi-domain, routing, trap (the right answer is "there is nothing")
  and adversarial (for example a prompt injection, where no specialist should be called). The table
  shows a score per kind.
- The full report is in `evals/report.json`: every answer, what was missing, and the `tools`
  trace of every call.

Show one improvement cycle on screen: pick a ✗ row, read its `missing` and `tools` in the report,
change one sentence in a prompt, `make eval Q=<id>`, then `make eval` for regressions. If the
room shares one key, tell people to use `make eval P=2`.

When you're ready to start the competition, put the Drive folder link on screen and say:

```bash
make submit NAME="your name or team"
```

- It zips `my_agent/` into `submission/<name>.zip`, which they upload to the Drive folder.
- You judge every submission on the hidden set with the same model and key, and only their
  `my_agent/` folder counts. They can upload again until the deadline; the newest upload counts.
- Put `platform/.judge/leaderboard.html` on the projector. It refreshes itself as results come in.
- Rules: don't hard-code answers, and marketing tools only read marketing data.

## 9. Wrap-up: the final question (3 min)

Ask *"Was the Nimbus Go launch campaign worth the money?"* on screen. Read the answer with the
room against exercise 5's "The final question" table: it should give the spend, the 18 sign-ups and
the cost per sign-up, and say the data can't show what those clients trade.

- Agents as tools: `AgentTool` gives you hierarchy, parallelism and sequencing from plain function
  calling.
- Two ways to give an agent skills: tools as data (a registry plus a hot-reloading `BaseToolset`) and
  tools as Python functions (signature + docstring). Both share one SQL guard and one read-only role.
- A new specialist is one module and one line in `SPECIALISTS`. The orchestrator, tracing and UI pick
  it up from there.
- Evals turn "it seems to work" into a score you can compare after every change.
- Repo: one `make up`, 100% synthetic data, runs on Docker.

## Troubleshooting on stage

| Symptom | Fix |
|---|---|
| "LLM key: missing" on Overview | `.env` has no key. Fix it and restart with `make up`. |
| Marketing node still dashed | `marketing_agent` is not in `SPECIALISTS`, or the app has not reloaded yet. Check `make logs`. |
| `make eval` stops with "build() isn't finished yet" | `marketing_agent` is in `SPECIALISTS` but exercise 2 isn't done. Finish `build()`, or take it out of the list for now. |
| `make eval` or `make check-N` says the agents don't build | Usually a syntax error in `my_agent/marketing_agent.py`. The message names it; `make logs` shows more. |
| `make submit` asks for a name | Run it with one: `make submit NAME="Ada Lovelace"`. |
| A leaderboard row says "no team.py inside" | They uploaded the wrong folder. Ask them to run `make submit` and upload that zip. |
| Old data or tools | `make reset` reloads the CSVs. `make -C platform seed-tools` re-applies the starter YAML. |
| Port 5432 busy | Set `POSTGRES_PORT=5433` in `.env`. |
