# Exercise 5: Prove it

[Back to the workshop](../WORKSHOP.md) · [Previous: Teamwork](4-teamwork.md)

## The problem

Every change you make to a prompt or a docstring fixes one question and can quietly break
another. Trying things by hand in the chat doesn't tell you which. You need a score.

## What helps

An **eval** is a fixed set of questions with known right answers. You run all of them after
every change and compare scores.

Run the practice set:

```bash
make eval
```

You get one row per question:

```
question                         kind          route  answer  note
uk-social-august                 lookup          ✓      ✓
cps-drop-q2-q3                   analysis        ✓      ✗    number 978.91
sg-marketing-booked              routing         ✗      ✓    called ['finance_agent', 'marketing_agent']
...
Score: 21 / 34   (an example)
```

Each question is worth two points:

- **route**: the orchestrator called exactly the right agents. Missing agents cost the point, and
  so do extra ones.
- **answer**: the answer passed every check on the question. Depending on the question, that
  means the right numbers (within 1%), certain words, or none of the phrases it shouldn't say.
  For trap questions, an LLM judge decides, using a one-line rule.

The questions come in six kinds: lookups, analysis, multi-domain, routing, traps and
adversarial. The full report, with every answer, is in `evals/report.json`. To re-run one
question, use `make eval Q=cps-drop-q2-q3`.

Don't expect full marks. The questions are meant to be hard.

## The competition

When the facilitators give the signal, they'll put a passphrase on the screen. Then run the
hidden set:

```bash
make eval-final KEY=<the passphrase>
```

It works like `make eval`, with harder questions you haven't seen. It shows only ids and ticks,
never the questions. Tell your facilitators your score when they ask. Highest score wins.

**You may change anything in your fork.** A few places to look:

<details>
<summary>Idea: more tools</summary>

The data team wrote five queries and you've used two. Which questions would the other three have
answered? Check the rows you lost points on.

</details>

<details>
<summary>Idea: better descriptions and docstrings</summary>

If the right agent was called but the answer was wrong, the agent probably picked the wrong tool
or the wrong dates. If the wrong agent was called, look at the descriptions and the routing rules.

</details>

<details>
<summary>Idea: the agent's own instruction</summary>

`prompts/marketing_agent.md` decides how your agent answers. The answer must contain the actual
figure, so ask for exact numbers rather than rounded ones. Some questions have no data behind
them. What should the agent say then?

</details>

<details>
<summary>Idea: teach finance new skills</summary>

The finance agent's tools live in the database, and you can add more from the **Tools** page
without writing Python. Its starter tools only report marketing costs by category, so none of
them returns account 5200, "Performance marketing", on its own.
[docs/EXTRA_UI_TOOLS.md](../docs/EXTRA_UI_TOOLS.md) shows how.

</details>

**Rules:**

- Keep the default model, so everyone competes on agent design.
- Don't hard-code answers. The hidden questions are different, so it wouldn't help anyway.
- Your marketing tools only read the marketing data. When a question needs finance or trading
  numbers, the orchestrator has to ask those agents.

## Read more

- [Why evaluate agents](https://google.github.io/adk-docs/evaluate/) in the ADK docs

Good luck. Vernon's review is on Friday.
