# Exercise 2: Hire the marketing agent

[Back to the workshop](../README.md) · [Previous: Give the data a voice](1-tools.md)
## The problem

Tools don't run themselves. Something has to read Vernon's question, choose a tool, fill in the
arguments, read the rows that come back and write an answer. In ADK that something is an agent.

## What helps

An `LlmAgent` is a model plus a job description. The fields that matter most:

- `name`: how other agents refer to it;
- `description`: what **other agents** read about it, to decide whether to send it work;
- `instruction`: what the **agent itself** reads, about how to do its job;
- `tools`: the functions it can call;
- `model`: which model does the thinking.

People mix up the description and the instruction all the time. The description faces outward:
a short pitch, written for whoever might delegate work. The instruction faces inward: rules for
the agent, like "only state numbers your tools returned".

```python
librarian = LlmAgent(
    name="librarian",
    model=MODEL,
    description="Finds books in the city library catalogue by title, author or topic.",
    instruction="Search the catalogue before answering. If a book isn't there, say so.",
    tools=[search_catalogue, check_availability],
)
```

## Your task

In the same file, **`my_agent/marketing_agent.py`**, finish the marketing agent:

1. Write its `DESCRIPTION`. Remember who reads it: the orchestrator, deciding whether a question
   belongs to marketing.
2. Make `build()` return an `LlmAgent` that uses your two tools and the three ready-made ones
   (`*READY_MADE_TOOLS`).

You don't need to write the instruction from scratch. It's waiting for you in a prompt file, and
you'll get to tune it in the competition.

`build()` takes `services` and `model`. Every specialist has this same signature, so the team can
build them all the same way. Finance and trading use `services` to reach their tools in the
database. Yours doesn't need it, so leave it unused.

<details>
<summary>Hint: where does the instruction come from?</summary>

`static_instruction(NAME)` loads `my_agent/prompts/marketing_agent.md` and fills
in today's date. It's already imported in `marketing_agent.py`.

</details>

<details>
<summary>Hint: how do the other specialists do it?</summary>

Look at `finance_agent.py` and `trading_agent.py` in `platform/src/devfest_agents/agents/`. Their
tools come from the database instead of Python, but their `DESCRIPTION`s show the style.
`GENERATION` sets a low temperature, so answers stay consistent from run to run.

</details>

<details>
<summary>Hint: show me build()</summary>

```python
def build(services: Any, model: Any) -> LlmAgent:
    return LlmAgent(
        name=NAME,
        model=model,
        description=DESCRIPTION,
        instruction=static_instruction(NAME),
        tools=[campaign_performance, channel_summary, *READY_MADE_TOOLS],
        generate_content_config=GENERATION,
    )
```

</details>

## Check it

```bash
make check-2
```

It builds your agent the way the app will, and checks its name, description, instruction and
tools. Then it asks your agent one question **on its own**, with no orchestrator in between:

```
  Asking your agent on its own: "Which campaign brought in the most new clients in August 2026, and how many?"
  ✓ It picked a tool: campaign_performance(start_date='2026-08-01', end_date='2026-08-31')
  ✓ It found the right answer (NM-INTL's social ads campaign, 6 new clients)
```

You can see which tool it picked from your docstrings, and whether the answer was right. This
takes about 10 seconds. If it picks a different tool or gets the answer wrong, read that tool's
docstring again.

## Read more

- [LLM agents](https://google.github.io/adk-docs/agents/llm-agents/) in the ADK docs

## Next

Your agent works, but only on its own: the chat still can't reach it. In
**[exercise 3](3-orchestrator.md)** you introduce it to the orchestrator.
