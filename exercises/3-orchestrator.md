# Exercise 3: Join the team

[Back to the workshop](../README.md) · [Previous: Hire the marketing agent](2-agent.md)

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

Two small edits, in two files:

1. **`my_agent/team.py`**: add your agent to `SPECIALISTS`, the team list.
   Every agent in that list becomes a tool for the orchestrator.
2. **`my_agent/prompts/orchestrator.md`**: this is the orchestrator's
   instruction. It lists every specialist under `## Specialists`. Add a line for yours. Then
   delete the `## Not covered yet` section you saw in exercise 0: campaigns are covered now.

Then ask in the chat:

> How much did our ad campaigns spend in Q3 2026?

The route panel should show the orchestrator calling `marketing_agent`, and your tool doing the
work. Give it 20 seconds or so: three agents think in turn.

<details>
<summary>Hint: how does the team list work?</summary>

Import your module at the top of `team.py` (`from . import marketing_agent`), then add it to the
list.
`build_root_agent()` builds every module in the list and wraps each one in an `AgentTool`.

</details>

<details>
<summary>Hint: what should the line say?</summary>

Write it in the same style as the finance and trading lines. Below that list, the orchestrator
also gets a live list of every specialist's tools, built from the first line of each docstring.
Your tools appear there on their own.

</details>

<details>
<summary>Hint: show me the changes</summary>

In `my_agent/team.py`:

```python
from devfest_agents.agents import finance_agent, trading_agent

from . import marketing_agent

SPECIALISTS = [finance_agent, trading_agent, marketing_agent]
```

In `my_agent/prompts/orchestrator.md`, under `## Specialists`:

```markdown
- `marketing_agent` - ad campaigns: spend per campaign or channel, impressions, clicks, the new
  clients each campaign brought in, cost per sign-up. Data: the `marketing` schema.
```

And delete the whole `## Not covered yet` section, heading included.

</details>

## Check it

```bash
make check-3
```

This one asks the agents a real question, so it takes about 30 seconds. Refresh the Overview page
too. Your agent is no longer dashed.

## Read more

- [Multi-agent systems](https://google.github.io/adk-docs/agents/multi-agents/) in the ADK docs,
  especially "agent as a tool"

## Next

Simple marketing questions work. Vernon's Friday questions aren't simple: they need marketing
and finance and trading at once, and some of them *sound* like marketing but aren't. That's
**[exercise 4](4-teamwork.md)**.
