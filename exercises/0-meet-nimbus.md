# Exercise 0: Meet Nimbus

[Back to the workshop](../README.md) · About 4 minutes

## The problem

Before fixing anything, see it break the way Vernon did.

## Look around

Open http://localhost:8080.

1. **Overview** shows the agents. The marketing agent is drawn with a dashed line, because it
   doesn't exist yet.

2. On the **Chat** page, ask what Vernon asked:

   > How did the Nimbus Go campaigns do?

   Watch the **Agent route** panel. The main agent passes the question to the orchestrator, and
   the orchestrator sends it to nobody. The assistant says it can't answer campaign questions.

   That refusal is deliberate. Open `my_agent/prompts/orchestrator.md`, the orchestrator's
   instruction, and find `## Not covered yet`. Finance knows what marketing cost in total, and
   trading knows who signed up, but neither can tell one campaign from another. Without that
   section, the orchestrator would stitch their partial answers together and present them as if
   they answered the question. You'll delete it in exercise 3, once a real marketing agent exists.

3. Open `my_agent/marketing_queries.py`, the data team's handover. Skim the `fetch_...` functions
   at the bottom: their names, their parameters, and the comment under each one. That's all your
   tools need. You won't change this file, and you can skip the SQL.

## Check it

```bash
make check-0
```

It checks that your LLM key is set and the marketing data is loaded.

## Next

The data team's queries return the right numbers, but Gemini can't use them yet. In
**[exercise 1](1-tools.md)** you turn two of them into tools.
