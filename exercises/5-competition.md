# The competition

[Back to the workshop](../README.md) · [Previous: Routing across agents](4-routing.md)

## The problem

Your agent passed every check. That shows it works on the questions you tried. The competition
asks questions you haven't seen.

## How it's scored

The facilitators keep a secret set of questions about Nimbus Markets, in the same style as the
exercises: marketing lookups, some maths, questions that need marketing together with finance or
trading, questions that sound like marketing but aren't, and a few traps. Each question is worth
5 marks:

- **1 for the route**: the orchestrator called exactly the right specialists. A missing one costs
  the mark, and so does an extra one.
- **4 for the answer**: an LLM judge checks the answer against 4 criteria, one mark each. The
  criteria ask for the right figures (within 1%) and the figures behind them, the right period
  and entity, and for traps, saying there's no data instead of making a number up.

Answers are marked on what they show, so ask your agent for exact figures, and for the figures
behind any result it works out.

## Practise

Five practice questions in the same style are in `evals/practice.yaml`, each with its 4 criteria.
Score your agent on them:

```bash
make eval
```

It asks one question at a time, so a free key never hits its limit, and takes about 3 minutes. You
get one row per question:

```
question                         kind          route  answer  note
cps-drop-q2-q3                   analysis        ✓     3/4    It names social but gives the fall as $1,203.40.
sg-marketing-booked              routing         ✗     4/4    called ['finance_agent', 'marketing_agent']
...
Score: 19 / 25   (an example)
```

`evals/report.json` has every answer, each criterion's verdict, and every tool call. While you fix
one question, run just that one: `make eval Q=cps-drop-q2-q3`. Run the full set to confirm.

Then ask the chat questions you think the hidden set might ask, and watch the **Agent route**
panel:

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

## Run the competition

At the end of the session, the facilitators show a passphrase and a link to a form. Run:

```bash
make eval-final KEY="<the passphrase>" NAME="Ada Lovelace"
```

It asks your agents the 5 hidden questions, one at a time, and writes their answers to
`evals/submission.json`. It takes about 3 minutes on a free key.
It shows no score: the facilitators score every file the same way, after the deadline. Upload
`evals/submission.json` to the [competition's form](https://forms.gle/ZuaxdysyoGR57Knz6).

- **One run.** Once you have the passphrase, the questions are out, so don't change your agent and
  run again. If a question fails (a rate limit or a timeout, say), it retries that question by
  itself, up to 3 times, and keeps the answers it already has.

Highest score wins, and the top 3 win a prize. On a tie, the earlier upload wins.

## The final question

One question in the hidden set is one you already know:

> Was the Nimbus Go launch campaign worth the money?

A good answer gives the figures *and* says what the data can't show. When the facilitators
announce the top 3, they read out the winner's answer to it.

## Read more

- [Why evaluate agents](https://google.github.io/adk-docs/evaluate/) in the ADK docs
