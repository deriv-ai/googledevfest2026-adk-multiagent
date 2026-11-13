# Exercise 3: Adding an agent to the orchestrator

[Back to the workshop](../README.md) · [Previous: Creating an agent](2-agent.md)

## The problem

The orchestrator only sends work to the specialists it knows about. Right now that's finance,
trading and news. Your agent needs to be on the list, and the orchestrator needs to know what
it's for.

## What helps

ADK can wrap a whole agent as a tool, with `AgentTool`. To the orchestrator, each specialist then
looks like one more function it can call, such as `marketing_agent(request="...")`.

That means there's no separate classifier deciding where a question goes. **Routing is function
calling.** When the orchestrator's model picks which functions to call, it reads three things
about each specialist:

1. **Its `DESCRIPTION`**, which ADK turns into the function's description. You wrote this in
   exercise 2. It's the specialist's own pitch.
2. **Its line in the orchestrator's instruction**, under `## Specialists`. This is the
   orchestrator's own view of the team: who covers what, and later, who wins when two overlap.
3. **A live list of the specialist's tools**, under `## What each specialist can do right now`.
   The app builds it from the first line of each tool's docstring every time a question comes
   in, so your tools show up there on their own.

The description says what an agent offers. The orchestrator's instruction says how to choose
between agents. You'll write the second kind in this exercise and the next.

```python
flights = LlmAgent(name="flights_agent", description="Finds and prices flights.", ...)
hotels = LlmAgent(name="hotels_agent", description="Finds and prices hotels.", ...)

concierge = LlmAgent(
    name="concierge",
    model=MODEL,
    instruction="Plan trips. Ask flights_agent about flights and hotels_agent about hotels.",
    tools=[AgentTool(agent=flights), AgentTool(agent=hotels)],
)
```

## Your task

Two small edits, in two files:

1. **`my_agent/team.py`**: import your module (`from . import marketing_agent`) and add it to
   `SPECIALISTS`, the team list. Every agent in that list becomes a tool for the orchestrator.
2. **`my_agent/prompts/orchestrator.md`**: this is the orchestrator's
   instruction. It lists every specialist under `## Specialists`. Add a line for yours, in the
   same style: what it covers and which data it reads. Then delete the `## Not covered yet`
   section you saw in exercise 0, heading included: campaigns are covered now.

Then ask the question from exercise 0 again, in a new chat:

> How did the Nimbus Go campaigns do?

Last time the orchestrator refused. Now the route panel should show it calling
`marketing_agent`, and your tools doing the work. Give it 20 seconds or so: three agents think in
turn.

## Check it

```bash
make check-3
```

It checks the team list and the orchestrator's instruction, then asks the assistant a different
marketing question from the one you tried, for extra coverage. It takes about 30 seconds.
Refresh the Overview page too: your agent is no longer dashed.

## Read more

- [Multi-agent systems](https://google.github.io/adk-docs/agents/multi-agents/) in the ADK docs,
  especially "agent as a tool"

## Next

Simple marketing questions work. Many questions aren't simple: they need marketing
and finance and trading at once, and some of them *sound* like marketing but aren't. That's
**[exercise 4](4-routing.md)**.
