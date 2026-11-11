# Exercise 4: Teamwork

[Back to the workshop](../WORKSHOP.md) · [Previous: Join the team](3-orchestrator.md)

## The problem

Vernon's real questions cross teams:

> What did each new client cost us in Q3 2026, counting every client who signed up?

The campaign spend is marketing's. The count of *every* new client is trading's, because many
clients sign up without any campaign. The orchestrator has to ask both and combine the answers.

Worse, some words mean different things to different teams. "Marketing spend" in the ledger is
finance's number, and it includes brand events and partner fees. "Campaign spend" is
marketing's. "New clients" is trading's, while "sign-ups from campaigns" is marketing's. A
confused orchestrator calls the wrong agent, or calls all three just in case.

## What helps

The orchestrator makes two kinds of calls:

- **Parallel**: when two sub-questions don't depend on each other, the model asks for both in
  the same step and ADK runs them at the same time.
- **Sequential**: when the second question needs the first answer ("which entity got the most
  sign-ups, and how much commission did *that* entity earn?"), it asks one, reads the answer,
  then asks the other.

Each specialist gets a rewritten, self-contained question with explicit dates. Specialists never
see the chat, so "last quarter" has to become "1 July to 30 September 2026".

When two specialists overlap, a **tie-break rule** in the orchestrator's instruction tells it who
owns what:

```markdown
Flight *prices* go to flights_agent. *Total trip cost* needs flights_agent and hotels_agent,
asked in parallel.
```

## Your task

Teach the orchestrator where marketing ends and finance and trading begin. Add tie-break rules
to its instruction.

Then try these in the chat, and watch the route panel:

| Question | Should go to |
|---|---|
| What did each new client cost us in Q3 2026, counting every client who signed up? | marketing and trading, in parallel |
| What was NM-SG's total Marketing expense booked in the ledger in September 2026? | finance only |
| How many new clients signed up in September 2026, whether or not a campaign brought them in? | trading only |
| Which entity's campaigns brought in the most sign-ups in Q3 2026, and how much commission did that entity's clients generate? | marketing, then trading |

<details>
<summary>Hint: where do the rules go?</summary>

`src/devfest_agents/agents/prompts/orchestrator.md`, under `## Routing rules`. Rule 1 already has
a tie-break for finance and trading. Put yours next to it.

</details>

<details>
<summary>Hint: show me rules that work</summary>

```markdown
   Spend *per campaign or channel* is marketing; marketing costs *as booked in the ledger* and
   marketing budgets are finance. Sign-ups *credited to a campaign* are marketing; *all* new clients
   are trading.
```

</details>

## Check it

```bash
make check-4
```

It asks three of the questions above and checks who answered.

## Read more

- [Multi-agent systems](https://google.github.io/adk-docs/agents/multi-agents/) in the ADK docs

## Next

It works on the questions you tried. Does it work on the ones you didn't? In
**[exercise 5](5-evals.md)** you find out, and the competition starts.
