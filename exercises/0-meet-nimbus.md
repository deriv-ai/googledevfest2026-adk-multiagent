# Exercise 0: Meet Nimbus

[Back to the workshop](../WORKSHOP.md)

## The problem

Before fixing anything, see it break the way Vernon did.

## Look around

Open http://localhost:8080.

1. **Overview** shows the agents. The marketing agent is drawn with a dashed line, because it
   doesn't exist yet.
2. **Chat** is where Vernon asks questions. Try a finance one first, so you've seen it work:

   > What was our operating profit in each month of Q3 2026?

   Watch the **Agent Route** panel on the right. The question goes from the main agent to the
   orchestrator, then to the finance agent, then to a tool that queries the database.

3. Now ask what Vernon asked:

   > How did the Nimbus Go campaigns do?

   The orchestrator has nobody to send it to, so the assistant says it can't help.

4. **Data Schema → marketing** shows the data your agent will use. There are three tables:
   campaigns, what each campaign spent, and the new clients each campaign brought in. Click a
   table to see its columns and a few rows.

5. Finally, open `src/devfest_agents/agents/marketing_queries.py`. This is the data team's
   handover. Skim it. You won't change it, and you don't need to understand the SQL.

## Check it

```bash
make check-0
```

This checks that your LLM key is set and the marketing data is loaded.

Curious where you stand? Run `make eval`. Expect a low score for now. That's the point.

## Next

The data team's queries return the right numbers, but Gemini can't use them yet. In
**[exercise 1](1-tools.md)** you turn them into tools.
