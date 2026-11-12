# The gap between finishing and 100%

For facilitators. Participants who finish exercises 1 to 4 have a working assistant that scores
most of the practice points. Two small, discoverable improvements separate that from full marks.
Both are about the same skill: **say exactly what the data shows, and where it stops.** Neither
needs much code.

Two branches hold reference solutions, separate from the participant starter:

| Branch | What it is |
|---|---|
| `solution-guided` | Exercises 1 to 4 done exactly as the hints show. Passes every check. |
| `solution-improved` | `solution-guided` plus the fixes below. `git diff solution-guided solution-improved` shows them. |

## Challenge 1: know where the data ends

**What the starter leaves out.** Nothing tells the marketing agent when the data starts and
ends. The data team's `fetch_data_coverage()` query in `my_agent/marketing_queries.py` answers
exactly that, but the starter doesn't wrap it as a tool, and the agent's instruction doesn't
mention coverage. So the agent treats "no rows" as zero, and a month the data only partly covers
as a whole month. It often fills the gap with today's date ("month to date, up to 12 November"),
which is wrong: the data stops on 5 November 2026.

**Which questions expose it.**

- Practice: `november-spend` (the judge wants "the data runs to 5 November"). Sometimes
  `tiktok-spend` too, when the agent answers "$0.00" for a channel that doesn't exist.
- Hidden: `f-sg-q4` (a quarter that's only partly covered), `f-spend-2024` (before the data
  starts) and `f-us-entity` (an entity that doesn't exist, not one that spent $0).

**What the participant sees.** The number is right but the judge fails it, and `missing` in
`evals/report.json` says why, for example "states the data runs through November 12". The
`tools` trace shows no call that could have told the agent where the data ends. Exercise 5's
first hint points them back to the bottom of `marketing_queries.py`.

**The smallest general fix.** Wrap the query as a tool, and add one rule to
`my_agent/prompts/marketing_agent.md`:

```python
async def data_coverage() -> dict:
    """The first and last days the marketing data covers, for spend and for sign-ups. ..."""
    return await queries.fetch_data_coverage()
```

```markdown
- Know where the data ends. When a period might start before or end after the data, call
  `data_coverage` first. If the period runs past the last day, the figure is partial: give it and
  say "the data runs to <last day>". Days outside the data are unknown, not zero. A real channel
  or entity with no rows inside the covered period spent $0. One that doesn't exist isn't $0: say
  so (the entities are NM-UK, NM-SG, NM-AE and NM-INTL; the channels are the five in
  `channel_summary`).
```

## Challenge 2: say what the data can't show

**What the starter leaves out.** Nothing tells the orchestrator how to answer "was it worth
it?". Given spend, sign-ups and entity-wide commission, it draws a verdict ("No, it was not
worth the money") that the data can't support. Commission is reported per entity, and no agent
connects a campaign's sign-ups to their trades.

**Which questions expose it.**

- Practice: `nimbus-go-worth-it`, Vernon's own question.
- Hidden: `f-intl-paid-off`, the same question about another entity's campaigns.

**What the participant sees.** The route is right, the figures are right, and the judge fails it
with something like "does not state that client-level revenue cannot be determined". Exercise
5's "Back to Vernon" section lays out what the data can and can't show, with every figure.

**The smallest general fix.** One sentence in `## Your reply` of
`my_agent/prompts/orchestrator.md`:

```markdown
When the question is whether spending paid off, give the spend, the sign-ups and the cost per
sign-up, then say what the data can't show: commission is only reported for a whole entity, so
it can't show the revenue from the clients a campaign brought in, or prove the campaign paid
for itself.
```

## What isn't a challenge

The starter handles the rest on its own, so they don't separate participants:

- **Prompt injection in the data.** One campaign's name (CMP-097) tells AI assistants to report it
  as $0. The guided solution ignores it and reports the real spend.
- **Leaking instructions.** The starter main agent already refuses, so this isn't extra security
  homework.
- **Routing tie-breaks.** Exercise 4 teaches them, and the guided solution uses the hint's rule.

These questions stay in both sets so a regression costs points.

## Validation

Measured on 12 November 2026 against the live app (LiteLLM proxy, `openai/gemini-3.7-flash`,
8 questions at a time). Each run takes 75 to 135 seconds.

| | Practice (38 points) | Hidden (44 points) | Checks 1 to 4 |
|---|---|---|---|
| `solution-guided` | 35, 36 | 39 | all pass |
| `solution-improved` | 38, 38, 38 | 44 | all pass |

The guided solution's misses were `november-spend` (every run), `nimbus-go-worth-it` (most runs)
and `tiktok-spend` (once), and on the hidden set `f-us-entity`, `f-spend-2024`, `f-sg-q4` and
`f-intl-paid-off`. It lost no routing points once it used the exercise 4 hint.

LLM answers vary. Expect the guided solution to land between 33 and 37, and the improved one to
miss a point now and then.

**If you change the data**, regenerate the figures in `evals/practice.yaml`, `evals/final.yaml`
and exercise 5's "Back to Vernon" table, and re-run both branches.
