# The competition

[Back to the workshop](../README.md) · [Previous: Routing across agents](4-routing.md)

## The problem

Your agent passed every check. That shows it works on the questions you tried. The competition
asks questions you haven't seen.

## How it's scored

The facilitators keep a secret set of questions about Nimbus Markets, in the same style as the
exercises: marketing lookups, some maths, questions that need marketing together with finance or
trading, questions that sound like marketing but aren't, and a few traps. You never run it
yourself. The facilitators run it on your `my_agent/` folder, with the same model and key for
everyone.

Each question is worth two points:

- **route**: the orchestrator called exactly the right specialists. A missing one costs the
  point, and so does an extra one.
- **answer**: the answer is right. That means the right numbers (within 1%), the right words,
  and for some questions a one-line rule that an LLM judge applies.

Finishing exercises 1 to 4 gets you most of the points, not all of them. To get the rest, ask
the chat questions you think the hidden set might ask, and watch the **Agent route** panel:

- The wrong specialists were called: sharpen the routing rules in
  `my_agent/prompts/orchestrator.md`.
- The right specialist, but the wrong tool or dates: improve that tool's docstring.
- The right data, but the answer gets it wrong: change the agent's instruction,
  `my_agent/prompts/marketing_agent.md`.
- No tool can answer it: write one. `my_agent/marketing_queries.py` has a query you haven't
  used yet.

Don't hard-code answers: the hidden questions are different, so it wouldn't help. Your marketing
tools read only the marketing data. When a question needs finance or trading numbers, the
orchestrator has to ask those agents.

## Submit

Zip your folder with your name or your team's name:

```bash
make submit NAME="Ada Lovelace"
```

That makes `submission/Ada Lovelace.zip`. Upload it to the
[competition's Google Drive folder](https://drive.google.com/drive/folders/DRIVE_FOLDER_ID).

You can upload again until the deadline: run `make submit` again and upload the new zip. Your
newest upload counts. Highest score wins; on a tie, the earlier upload wins.

## The final question

The last question in the hidden set is one you already know:

> Was the Nimbus Go launch campaign worth the money?

A good answer gives the figures *and* says what the data can't show. The facilitators go
through the answer at the wrap-up.

## Read more

- [Why evaluate agents](https://google.github.io/adk-docs/evaluate/) in the ADK docs
