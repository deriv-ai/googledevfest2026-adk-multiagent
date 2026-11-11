# Exercise 2: Hire the marketing agent

[Back to the workshop](../WORKSHOP.md) · [Previous: Give the data a voice](1-tools.md)

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

In the same file, **`src/devfest_agents/agents/marketing_agent.py`**, finish the marketing agent:

1. Write its `DESCRIPTION`. Remember who reads it: the orchestrator, deciding whether a question
   belongs to marketing.
2. Make `build()` return an `LlmAgent` that uses your two tools.

You don't need to write the instruction from scratch. It's waiting for you in a prompt file, and
you'll get to tune it in the competition.

<details>
<summary>Hint: where does the instruction come from?</summary>

`static_instruction(NAME)` loads `src/devfest_agents/agents/prompts/marketing_agent.md` and fills
in today's date. It's already imported in `marketing_agent.py`.

</details>

<details>
<summary>Hint: how do the other specialists do it?</summary>

Look at `finance_agent.py` and `trading_agent.py` next to your file. Their tools come from the
database instead of Python, but their `DESCRIPTION`s show the style. `GENERATION` sets a low
temperature, so answers stay consistent from run to run.

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
        tools=[campaign_performance, channel_summary],
        generate_content_config=GENERATION,
    )
```

</details>

## Check it

```bash
make check-2
```

It builds your agent the way the app will, and checks its name, description, instruction and
tools.

## Read more

- [LLM agents](https://google.github.io/adk-docs/agents/llm-agents/) in the ADK docs

## Next

Your agent exists, but nobody on the team knows. Ask a marketing question in the chat now and
you'll still get "no one here covers that". In **[exercise 3](3-orchestrator.md)** you introduce
it to the orchestrator.
