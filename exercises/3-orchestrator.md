# Exercise 3: Join the team

[Back to the workshop](../WORKSHOP.md) · [Previous: Hire the marketing agent](2-agent.md)

## The problem

The orchestrator only sends work to the specialists it knows about. Right now that's finance and
trading. Your agent needs to be on the list, and the orchestrator needs to know what it's for.

## What helps

ADK can wrap a whole agent as a tool, with `AgentTool`. To the orchestrator, each specialist then
looks like one more function it can call, such as `marketing_agent(request="...")`. The
specialist's description becomes the function's description.

That means there's no separate classifier deciding where a question goes. **Routing is function
calling.** The orchestrator's model reads the descriptions, reads its own instruction, and picks
which functions to call.

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

1. Add your agent to the team, so the orchestrator gets it as a tool.
2. Tell the orchestrator what marketing covers. Its instruction lists every specialist. Add a line
   for yours.

Then ask in the chat:

> How much did our ad campaigns spend in Q3 2026?

The route panel should show the orchestrator calling `marketing_agent`, and your tool doing the
work.

<details>
<summary>Hint: where is the team list?</summary>

`SPECIALISTS` in `src/devfest_agents/agents/__init__.py`. Import your module next to the others
and add it to the list. `build_root_agent()` builds every module in the list and wraps each one in
an `AgentTool` for the orchestrator.

</details>

<details>
<summary>Hint: where is the orchestrator's instruction?</summary>

`src/devfest_agents/agents/prompts/orchestrator.md`, under `## Specialists`. Write a line in the
same style as the finance and trading ones. Below it, the orchestrator also gets a live list of
every specialist's tools, built from the first line of each docstring. Your tools appear there
on their own.

</details>

<details>
<summary>Hint: show me the changes</summary>

In `agents/__init__.py`:

```python
from . import finance_agent, main_agent, marketing_agent, orchestrator, trading_agent

SPECIALISTS = [finance_agent, trading_agent, marketing_agent]
```

In `prompts/orchestrator.md`, under `## Specialists`:

```markdown
- `marketing_agent` - ad campaigns: spend per campaign or channel, impressions, clicks, the new
  clients each campaign brought in, cost per sign-up. Data: the `marketing` schema.
```

</details>

## Check it

```bash
make check-3
```

This one asks the agents a real question, so it takes a few seconds. Refresh the Overview page
too. Your agent is no longer dashed.

## Read more

- [Multi-agent systems](https://google.github.io/adk-docs/agents/multi-agents/) in the ADK docs,
  especially "agent as a tool"

## Next

Simple marketing questions work. Vernon's Friday questions aren't simple: they need marketing
and finance and trading at once, and some of them *sound* like marketing but aren't. That's
**[exercise 4](4-teamwork.md)**.
