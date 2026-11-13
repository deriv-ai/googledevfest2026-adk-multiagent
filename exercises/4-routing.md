# Exercise 4: Routing across agents

[Back to the workshop](../README.md) · [Previous: Adding an agent to the orchestrator](3-orchestrator.md)

## The problem

Most real questions cross teams:

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
- **Sequential**: when the second question needs the first answer ("when did the Nimbus Go
  campaigns first spend money, and what was NM-SG's operating profit in *that* month?"), it asks
  one, reads the answer, then asks the other.

Each specialist gets a rewritten, self-contained question with explicit dates. Specialists never
see the chat, so "last quarter" has to become "1 July to 30 September 2026".

Combining answers often means a calculation, such as spend divided by new clients. That's fine:
the agents may calculate, as long as every input comes from a tool and the answer shows the sum,
like `$117,844.95 / 113 new clients = $1,042.88`. The prompts you were given already say so.

When two specialists overlap, a **tie-break rule** in the orchestrator's instruction tells it who
owns what:

```markdown
Flight *prices* go to flights_agent. *Total trip cost* needs flights_agent and hotels_agent,
asked in parallel.
```

## Your task

Teach the orchestrator where marketing ends and finance and trading begin. Open
**`my_agent/prompts/orchestrator.md`** again and add tie-break rules under
`## Routing rules`. Rule 1 already has one for finance and trading. Put yours next to it.

Then try these in the chat, and watch the route panel:

| Question | Should go to |
|---|---|
| What did each new client cost us in Q3 2026, counting every client who signed up? | marketing and trading, in parallel |
| What was NM-SG's total Marketing expense booked in the ledger in September 2026? | finance only |
| How many new clients signed up in September 2026, whether or not a campaign brought them in? | trading only |
| When did the Nimbus Go launch campaigns first spend money, and what was NM-SG's operating profit in that month? | marketing, then finance |

## Check it

```bash
make check-4
```

It asks three of the questions above, about a minute in all. For each one it checks that the
right specialists were called and that the answer is right. It also checks *how* they were called:

- **Parallel**: both specialists were asked in the same step, before either answered.
- **Sequential**: the second specialist was asked only after the first answered, about what the
  first one found (here, the month).

Calling the right agents in the wrong order doesn't pass.

## Read more

- [Multi-agent systems](https://google.github.io/adk-docs/agents/multi-agents/) in the ADK docs

## Next

It works on the questions you tried. Does it work on the ones you didn't? In
**[the competition](5-competition.md)** you find out.
