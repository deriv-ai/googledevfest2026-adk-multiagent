# Exercise 5: Prove it

[Back to the workshop](../README.md) · [Previous: Teamwork](4-teamwork.md)

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

It takes a minute or two. Then you get one row per question:

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

The competition uses a hidden set of harder questions in the same style. You never run it
yourself. The facilitators run it on your code, the same way for everyone: same model, same key,
and only your `my_agent/` folder.

1. Commit and push your work:

   ```bash
   git add my_agent
   git commit -m "My agent"
   git push
   ```

2. Check it's ready, and get what to hand in:

   ```bash
   make submit
   ```

   It prints your fork's URL and your commit.

3. Paste both into the form your facilitators shared.

You can submit again until the deadline. Your last submission counts. The leaderboard is on the
screen and fills in as the facilitators judge. Highest score wins, and on a tie the earlier
submission wins.

**You may change anything in `my_agent/`.** Only that folder is judged. A few places to look:

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

`my_agent/prompts/marketing_agent.md` decides how your agent answers. The answer must contain the actual
figure, so ask for exact numbers rather than rounded ones. Some questions have no data behind
them. What should the agent say then?

</details>

<details>
<summary>Idea: guard the front door</summary>

Some questions try to get the assistant to leak its instructions, play a role, or do something it
shouldn't. The first agent to read every question is the main agent, and its prompt is
`my_agent/prompts/main_agent.md`. What should it refuse, whatever the framing?

</details>

<details>
<summary>Idea: data can lie too</summary>

Your tools return text that someone else wrote, like campaign names. To a model, text in a tool
result looks a lot like an instruction. Tell your agent to treat what tools return as data.

</details>

**Rules:**

- Don't hard-code answers. The hidden questions are different, so it wouldn't help anyway.
- Your marketing tools only read the marketing data. When a question needs finance or trading
  numbers, the orchestrator has to ask those agents.

## Go further

The score isn't everything. If you'd rather explore, here are some things ADK can do that this
workshop hasn't touched:

- **Callbacks.** ADK can run your code before or after every tool call. Write a
  `before_tool_callback` that blocks any call with a date range longer than a year.
- **Another specialist.** Add an agent of your own to `SPECIALISTS`, such as a "board report"
  agent that has no data and only writes Vernon's Friday summary from what the others found.
  The eval scores routing strictly, so an agent that joins every question costs you points.
- **ADK's own dev UI.** Open http://localhost:8000 and pick `nimbus`. It shows the raw events ADK
  produces for the same agents.

## Read more

- [Why evaluate agents](https://google.github.io/adk-docs/evaluate/) in the ADK docs
- [Callbacks](https://google.github.io/adk-docs/callbacks/) in the ADK docs

Good luck. Vernon's review is on Friday.
