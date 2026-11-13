# Exercise 2: Creating an agent

[Back to the workshop](../README.md) · [Previous: Creating tools](1-tools.md)

## The problem

Tools don't run themselves. Something has to read the question, choose a tool, fill in the
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
3. For its instruction, use `static_instruction(NAME)`. It loads
   `my_agent/prompts/marketing_agent.md`, so you don't write the instruction from scratch.
4. Pass `generate_content_config=GENERATION`. It sets a low temperature, so answers stay the same
   from run to run.

`static_instruction` and `GENERATION` are already imported in `marketing_agent.py`.

`build()` takes `services` and `model`. Every specialist has this same signature, so the team can
build them all the same way. Finance and trading use `services` to reach their tools in the
database. Yours doesn't need it, so leave it unused.

## Check it

```bash
make check-2
```

It builds your agent the way the app will, and checks its name, description, instruction and
tools. It doesn't ask your agent anything, so it costs nothing on your key and takes a few
seconds. Your agent answers its first real question in exercise 3, once the orchestrator can
reach it.

## Read more

- [LLM agents](https://google.github.io/adk-docs/agents/llm-agents/) in the ADK docs

## Next

Your agent works, but only on its own: the chat still can't reach it. In
**[exercise 3](3-orchestrator.md)** you introduce it to the orchestrator.
