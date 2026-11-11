# Workshop guide: add a marketing agent to a multi-agent system

Nimbus Markets is a made-up online broker. All of its data is fake.

Nimbus already has an AI assistant, built with [Google ADK](https://google.github.io/adk-docs/). The
assistant answers questions about **finance** and **trading**. It cannot answer questions about
**marketing**, because no agent knows the marketing data.

Your job is to build that marketing agent and plug it into the orchestrator. After that, the
assistant can answer marketing questions on their own, and questions that mix marketing with
finance or trading. At the end, you compete on a leaderboard of questions like that.

You will write about 80 lines of Python. Every step below has the code, so you can copy it if you
fall behind.

---

## Before the workshop

You need Docker (with Compose) or Podman (with `podman-compose`), `make`, git and a free Gemini key.

1. Fork this repo on GitHub, then clone your fork.
2. Copy the settings file: `cp .env.example .env`
3. Get a free key from [Google AI Studio](https://aistudio.google.com/apikey) and paste it after
   `GEMINI_API_KEY=` in `.env`.
4. Start everything: `make up` (Docker) or `make podman-up` (Podman). The first start builds the
   images and takes a few minutes.
5. Open http://localhost:8080. The **Overview** page shows the agents. The marketing agent is drawn
   with a dashed line: that is the one you build.

If you use Podman, add `ENGINE=podman` to the `make eval` and `make seed-tools` commands below.

---

## How the system works

```
main_agent ──> orchestrator ──> finance_agent   (tools: SQL queries stored in the database)
                            ├─> trading_agent   (tools: SQL queries stored in the database)
                            └─> marketing_agent (tools: Python functions you write)
```

- **main_agent** talks to the user. It sends every business question to the orchestrator.
- **orchestrator** decides which specialist agents a question needs. It calls them, then merges
  their answers.
- **finance_agent** and **trading_agent** are the specialists that exist today.
- **marketing_agent** is the specialist you add.

Four ADK ideas make this work. Each step below uses one of them.

1. **A tool is a Python function.** ADK reads the function's name, type hints and docstring, and
   turns them into a description that Gemini can call. The docstring is the prompt for the tool.
2. **An agent is an `LlmAgent`.** It has a name, a description, an instruction, a model and tools.
3. **An agent can be a tool for another agent.** ADK's `AgentTool` wraps a whole agent as one
   function. The orchestrator sees each specialist as a function such as
   `marketing_agent(request)`.
4. **Routing is function calling.** There is no separate classifier. The orchestrator's model reads
   each specialist's description and its own routing rules, then picks which functions to call.
   When it calls several functions in one step, ADK runs them in parallel.

The code you touch:

| File | What it is |
|---|---|
| `src/devfest_agents/agents/marketing_agent.py` | Your agent and its tools. Starts as a stub with TODOs. |
| `src/devfest_agents/agents/__init__.py` | The list of specialists the orchestrator can call. |
| `src/devfest_agents/agents/prompts/orchestrator.md` | The orchestrator's routing rules. |
| `src/devfest_agents/agents/prompts/marketing_agent.md` | Your agent's instruction. Already written. |

Read `finance_agent.py` and `trading_agent.py` for comparison. Their tools come from the database,
so their files are short.

You never restart anything. The app reloads by itself when you save a Python file. If the chat
stops answering after a save, run `make logs` to see the error.

---

## Step 0: see the gap

1. Open **Chat** and ask: *How much did our ad campaigns spend last quarter?*
2. Watch the **Agent Route** panel on the right. The orchestrator has no marketing specialist, so
   it says it cannot answer.
3. Open **Data Schema → marketing**. This is the data your agent will read:
   - `campaigns`: one row per campaign, for one entity and one ad channel.
   - `campaign_spend`: what each campaign spent, with impressions and clicks.
   - `signups`: which new clients each campaign brought in.

   Click a table to see its columns and five sample rows. The descriptions come from the database
   itself, so they are always correct.

---

## Step 1: write your first tool

Open `src/devfest_agents/agents/marketing_agent.py`. Replace the `TODO step 1` comment with this:

```python
CAMPAIGN_PERFORMANCE_SQL = """
WITH spend AS (
    SELECT s.campaign_id, SUM(s.spend_usd) AS spend_usd, SUM(s.impressions) AS impressions, SUM(s.clicks) AS clicks
    FROM marketing.campaign_spend s
    WHERE s.spend_date BETWEEN :start_date AND :end_date
    GROUP BY s.campaign_id
), signups AS (
    SELECT g.campaign_id, COUNT(*) AS signups
    FROM marketing.signups g
    WHERE g.signup_date BETWEEN :start_date AND :end_date
    GROUP BY g.campaign_id
)
SELECT c.campaign_id, c.name, c.entity_id, c.channel,
       COALESCE(sp.spend_usd, 0) AS spend_usd,
       COALESCE(sp.impressions, 0) AS impressions,
       COALESCE(sp.clicks, 0) AS clicks,
       COALESCE(su.signups, 0) AS signups,
       ROUND(sp.spend_usd / NULLIF(su.signups, 0), 2) AS cost_per_signup_usd
FROM marketing.campaigns c
LEFT JOIN spend sp ON sp.campaign_id = c.campaign_id
LEFT JOIN signups su ON su.campaign_id = c.campaign_id
WHERE (sp.campaign_id IS NOT NULL OR su.campaign_id IS NOT NULL)
  AND (:entity_id::text IS NULL OR c.entity_id = :entity_id)
ORDER BY spend_usd DESC
"""


async def campaign_performance(start_date: str, end_date: str, entity_id: str | None = None) -> dict:
    """Spend, clicks and sign-ups per campaign for a date range.

    One row per campaign: campaign_id, name, entity_id, channel, spend_usd, impressions,
    clicks, signups (new clients the campaign brought in) and cost_per_signup_usd.
    Use it for "how did our campaigns do last quarter?" or "how did the Nimbus Go campaigns do?".

    Args:
        start_date: First day, YYYY-MM-DD.
        end_date: Last day (inclusive), YYYY-MM-DD.
        entity_id: Only campaigns of this entity: NM-UK, NM-SG, NM-AE or NM-INTL. Omit for all.
    """
    return await run_sql("marketing", CAMPAIGN_PERFORMANCE_SQL,
                         start_date=start_date, end_date=end_date, entity_id=entity_id)
```

What each part does:

- **The SQL** adds up spend and sign-ups per campaign. `:start_date`, `:end_date` and `:entity_id`
  are placeholders. `run_sql` fills them from the keyword arguments you pass.
- **`:entity_id::text IS NULL`** makes the filter optional. The `::text` tells Postgres the type,
  because a bare `NULL` has no type.
- **`run_sql("marketing", ...)`** runs the query safely: read-only, with a 5-second timeout and a
  row limit, and only on the `marketing` schema. If something is wrong, it returns
  `{"error": "..."}`. The model reads that message and can try again.
- **The signature** (`start_date: str`, `entity_id: str | None = None`) becomes the tool's
  parameters. `None` as the default makes a parameter optional.
- **The docstring** is what Gemini reads to decide *when* to call the tool and *how* to fill the
  arguments. It is a prompt, so write it for the model. Say what the tool returns, when to use it,
  and the format of each argument.

---

## Step 2: write a second tool

Questions like *which channel works best?* need numbers per channel, not per campaign. The model
could add up the campaign rows itself, but models make mistakes with long sums. A tool that does
the sum in SQL is more reliable.

Replace the `TODO step 2` comment with this:

```python
CHANNEL_SUMMARY_SQL = """
WITH spend AS (
    SELECT c.channel, SUM(s.spend_usd) AS spend_usd, SUM(s.impressions) AS impressions, SUM(s.clicks) AS clicks
    FROM marketing.campaign_spend s
    JOIN marketing.campaigns c ON c.campaign_id = s.campaign_id
    WHERE s.spend_date BETWEEN :start_date AND :end_date
      AND (:entity_id::text IS NULL OR c.entity_id = :entity_id)
    GROUP BY c.channel
), signups AS (
    SELECT c.channel, COUNT(*) AS signups
    FROM marketing.signups g
    JOIN marketing.campaigns c ON c.campaign_id = g.campaign_id
    WHERE g.signup_date BETWEEN :start_date AND :end_date
      AND (:entity_id::text IS NULL OR c.entity_id = :entity_id)
    GROUP BY c.channel
)
SELECT sp.channel, sp.spend_usd, sp.impressions, sp.clicks,
       ROUND(100.0 * sp.clicks / NULLIF(sp.impressions, 0), 2) AS click_through_pct,
       COALESCE(su.signups, 0) AS signups,
       ROUND(sp.spend_usd / NULLIF(su.signups, 0), 2) AS cost_per_signup_usd
FROM spend sp
LEFT JOIN signups su ON su.channel = sp.channel
ORDER BY sp.spend_usd DESC
"""


async def channel_summary(start_date: str, end_date: str, entity_id: str | None = None) -> dict:
    """Spend, clicks and sign-ups per ad channel for a date range.

    One row per channel (search ads, social ads, video ads, app-store ads, affiliate network):
    spend_usd, impressions, clicks, click_through_pct, signups and cost_per_signup_usd.
    Use it for "which channel works best?" or "what did we spend on social ads?".

    Args:
        start_date: First day, YYYY-MM-DD.
        end_date: Last day (inclusive), YYYY-MM-DD.
        entity_id: Only campaigns of this entity: NM-UK, NM-SG, NM-AE or NM-INTL. Omit for all.
    """
    return await run_sql("marketing", CHANNEL_SUMMARY_SQL,
                         start_date=start_date, end_date=end_date, entity_id=entity_id)
```

The pattern is the same as step 1: SQL, a typed signature, and a docstring written for the model.

---

## Step 3: build the agent

Two TODOs are left in the file.

First, the description. Replace `DESCRIPTION = ""` with:

```python
DESCRIPTION = (
    "Marketing specialist for Nimbus Markets. Answers questions about ad campaigns: spend per campaign, "
    "channel or entity, impressions, clicks, the new clients campaigns brought in (sign-ups) and cost per "
    "sign-up. Pass one self-contained question with explicit dates."
)
```

The orchestrator never reads your code. It only reads this description, and it uses it to decide
when to call your agent. A vague description means wrong routing.

Then replace the body of `build()`:

```python
def build(services: Any, model: Any) -> LlmAgent:
    return LlmAgent(
        name=NAME,
        model=model,
        description=DESCRIPTION,
        instruction=static_instruction(NAME),
        tools=[campaign_performance, channel_summary],
        generate_content_config=GENERATION,
    )
```

What each field does:

- **`name`**: the agent's name. The orchestrator calls it as the function `marketing_agent`.
- **`model`**: the Gemini model. The app passes the same model to every specialist.
- **`description`**: what *other* agents read about this agent.
- **`instruction`**: what *this* agent reads about its own job. `static_instruction(NAME)` loads
  `prompts/marketing_agent.md` and fills in today's date. Open that file to see the rules.
- **`tools`**: your plain Python functions. ADK wraps each one as a `FunctionTool` for you.
- **`generate_content_config`**: a low temperature (0.2), so answers stay consistent.

---

## Step 4: plug the agent into the orchestrator

Two small edits.

**1. Add the agent to the list of specialists.** In `src/devfest_agents/agents/__init__.py`, import
your module and add it to `SPECIALISTS`:

```python
from . import finance_agent, main_agent, marketing_agent, orchestrator, trading_agent

# The agents the orchestrator can delegate to. Workshop step 4: add marketing_agent.
SPECIALISTS = [finance_agent, trading_agent, marketing_agent]
```

`build_root_agent()` builds every module in this list. It then hands the agents to the
orchestrator, wrapped as `AgentTool`s. The UI also reads this list, so your agent appears on the
Overview page.

**2. Teach the orchestrator when to use it.** In `src/devfest_agents/agents/prompts/orchestrator.md`:

Add a line under `## Specialists`:

```markdown
- `marketing_agent` - ad campaigns: spend per campaign or channel, impressions, clicks, the new
  clients each campaign brought in, cost per sign-up. Data: the `marketing` schema.
```

Add a tie-breaker under routing rule 1, because some questions sound like two domains at once:

```markdown
   Spend *per campaign or channel* is marketing; marketing costs *as booked in the ledger* and
   marketing budgets are finance. Sign-ups *credited to a campaign* are marketing; *all* new clients
   are trading.
```

And add `"Marketing: ..."` to the attribution example under `## Your reply`.

The orchestrator's instruction is rebuilt on every question. It includes a live list of every
specialist's tools, built from their names and the first line of each docstring. So your new tools
show up in routing without any extra work.

---

## Step 5: try it

Refresh http://localhost:8080. The marketing agent on the Overview page is now drawn normally.

Ask these in **Chat** and watch the **Agent Route** panel:

| Question | What to look for |
|---|---|
| *How much did our ad campaigns spend from July to September 2026?* | Only `marketing_agent` is called. Its tool shows the label **Python**. |
| *Which ad channel had the lowest cost per sign-up in Q3 2026?* | The model picks `channel_summary`, not `campaign_performance`. |
| *How many new clients signed up in Q3 2026, and how many came from campaigns?* | `trading_agent` and `marketing_agent` light up **at the same time**: a parallel call. |
| *Which entity's campaigns brought in the most sign-ups in Q3 2026, and how much commission did that entity's clients generate?* | Marketing first, then trading: a **sequential** call, because the second question needs the first answer. |
| *Was the Nimbus Go campaign worth the money?* | Marketing and finance together. Nimbus Go is a campaign in Singapore (NM-SG) that went far over budget. |

You can also open the ADK dev UI at http://localhost:8000 and pick the `nimbus` app. It shows ADK's
own view of the same agents.

---

## Step 6: score your agent

```bash
make eval
```

This runs every question in `evals/practice.yaml` through your agents and prints a score. Each
question is worth 2 points:

- **1 point for routing**: the orchestrator called exactly the expected agents. No missing agents,
  no extra ones.
- **1 point for the answer**: the final answer contains every expected number (within 1%) and
  every expected word.

The full report, with each answer and what was missing, is in `evals/report.json`. To re-run one
question, pass its id: `make eval Q=cheapest-channel-q3`.

With only the two tools from this guide, your agent will not get full marks. That is on purpose.
The rest is the competition.

---

## The competition

The leaderboard uses a **hidden** set of questions in the same style as `evals/practice.yaml`:
marketing questions on their own, and questions that mix marketing with finance or trading. Your
facilitators will tell you how to submit. The highest score at the end wins.

**You may change anything in your fork**, for example:

- **Add tools.** Look at the practice questions you lose points on. Is there a question no tool
  answers well? Common gaps: spend per month, totals per entity, the Nimbus Go campaigns as one
  group, comparing two periods.
- **Improve docstrings and descriptions.** The model only knows what you tell it. Say which tool to
  use for which kind of question.
- **Sharpen the routing rules** in `orchestrator.md`. Extra agents cost you the routing point, and
  so do missing ones.
- **Improve `marketing_agent.md`**, for example how to present numbers. The answer must contain the
  actual figure, so ask for exact numbers rather than rounded ones.
- **Teach finance and trading new skills.** Their tools live in the database, and you can add more
  from the **Tools** page with no Python at all (see `docs/WORKSHOP.md`). For example, the finance
  tools only report marketing costs by *category*, so no tool returns account 5200 "Performance
  marketing" on its own.

**Rules:**

- Keep the default model, so everyone competes on agent design, not on model choice.
- Don't hard-code answers. The hidden questions are different, so it would not help anyway.
- Your marketing tools may only read the `marketing` schema. `run_sql` enforces this. When an
  answer needs trading or finance data, the orchestrator must ask those agents.

---

## If you get stuck

- **The chat stopped answering after I saved a file.** You probably have a Python error. Run
  `make logs`, read the error, fix it and save again.
- **My tool returns an error.** The route panel shows the tool's result. Errors from `run_sql` say
  what is wrong, for example a table without its `marketing.` prefix, or a placeholder you did not
  pass a value for.
- **I fell behind.** The `solution` branch has steps 1 to 4 done. Copy the three files from it:

  ```bash
  git fetch origin solution
  git checkout origin/solution -- src/devfest_agents/agents/marketing_agent.py \
      src/devfest_agents/agents/__init__.py src/devfest_agents/agents/prompts/orchestrator.md
  ```

  If your fork has no `solution` branch, GitHub only copied `main` when you forked. Ask a
  facilitator for the workshop repo URL, then run `git remote add upstream <url>`, and use
  `upstream` instead of `origin` in the commands above.
- **The data looks wrong or old.** `make reset` (or `make podman-reset`) wipes the database and
  loads it again.

---

## What you learned

- A multi-agent system in ADK can be plain function calling: the orchestrator calls specialists
  that are wrapped as `AgentTool`s.
- A specialist is an `LlmAgent` with a description (for other agents), an instruction (for itself)
  and tools.
- A tool is a typed Python function, and its docstring is its prompt.
- Routing quality comes from clear, non-overlapping descriptions, plus explicit rules for the cases
  that overlap.
- Evals turn "it seems to work" into a score you can improve.
