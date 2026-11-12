# Exercise 5: Prove it

[Back to the workshop](../README.md) · [Previous: Teamwork](4-teamwork.md) · About 10 minutes,
then submit

## The problem

Your agent passed every check. That means it works on the questions you tried. Every change you
make to a prompt or a docstring can fix one question and quietly break another, and trying things
by hand in the chat won't tell you which. You need a score.

## Score it

An **eval** is a fixed set of questions with known right answers. You run all of them after
every change and compare scores.

```bash
make eval
```

It takes about 2 minutes. Then you get one row per question:

```
question                         kind          route  answer  note
uk-social-august                 lookup          ✓      ✓
cps-drop-q2-q3                   analysis        ✓      ✗    number 978.91
sg-marketing-booked              routing         ✗      ✓    called ['finance_agent', 'marketing_agent']
...
Score: 33 / 38   (an example)
```

Each question is worth two points:

- **route**: the orchestrator called exactly the right specialists. A missing one costs the
  point, and so does an extra one.
- **answer**: the answer passed every check on the question: the right numbers (within 1%),
  certain words, no forbidden phrases, and for some questions a one-line rule that an LLM judge
  applies.

Finishing exercises 1 to 4 gets you most of the points, not all of them. The rest is this
exercise.

**If `make eval` reports rate limits or lots of timeouts**, your key is busy (a shared key in a
full room, say). Run `make eval P=2` to ask 2 questions at a time instead of 8. It's slower, but
it finishes.

## Fix one failure

This is the loop you'll use for the rest of the session:

1. **Pick one ✗ row.** Open `evals/report.json` and find that question by its `id`. Read three
   fields: `answer` (what the assistant said), `missing` (which check failed and why) and `tools`
   (every call, in order: which agent called which tool, with which arguments). You can also ask
   the same question in the chat and watch the route panel.
2. **Find the cause.**
   - The wrong specialists were called: look at the routing rules in
     `my_agent/prompts/orchestrator.md`.
   - The right specialist, but the wrong tool or dates: look at that tool's docstring.
   - The right data, but the answer gets it wrong: look at the agent's instruction,
     `my_agent/prompts/marketing_agent.md`.
3. **Change one thing.** One sentence in a prompt, or a docstring, or a new tool.
4. **Re-run that question**: `make eval Q=<id>`. LLM answers vary a little, so if it passed,
   run it once more.
5. **Re-run everything**: `make eval`. Check that you didn't break anything else.

<details>
<summary>Hint: a number is right, but the judge says the period is wrong</summary>

The judge's rule is in `evals/practice.yaml`, under the question's `id`. Read it. Then ask
yourself: how would your agent know when the data starts and ends? Look at the bottom of
`my_agent/marketing_queries.py` again. There's a query you haven't used yet.

</details>

<details>
<summary>Hint: "Was the Nimbus Go launch campaign worth the money?" fails the judge</summary>

Read its judge rule in `evals/practice.yaml`, then [Back to Vernon](#back-to-vernon) below. A
good answer says what the data shows *and* what it can't show. Which agent writes the joined-up
answer, and whose instruction would you change?

</details>

**What the score can and can't tell you.** The checks are simple on purpose. A number counts if
it appears anywhere in the answer, so questions where the wrong number could slip in also have a
judge rule about what the number means. The judge is a model too: it's strict, but not perfect.
The route point is all or nothing. And the same agents can score a point or two differently from
one run to the next. Trust a change that helps over two runs, not one.

## The competition

The competition uses a hidden set of harder questions in the same style. You never run it
yourself. The facilitators run it on your `my_agent/` folder, with the same model and key for
everyone. Submit before 0:54 on the schedule:

```bash
git add my_agent
git commit -m "My agent"
git push
make submit
```

`make submit` checks your work is pushed and prints your fork's URL and commit. Paste both into
the form your facilitators shared. You can submit again until the deadline, and your last
submission counts. Highest score wins; on a tie, the earlier submission wins.

Don't hard-code answers: the hidden questions are different, so it wouldn't help anyway. Your
marketing tools read only the marketing data; when a question needs finance or trading numbers,
the orchestrator has to ask those agents.

## Back to Vernon

Ask the question from the start one last time:

> Was the Nimbus Go launch campaign worth the money?

Here's what the data can show, and what an honest answer does with it:

| What we know | Figure | Where it comes from |
|---|---|---|
| Spend on the Nimbus Go campaigns, 15 June to 5 November 2026 | $64,226.88 | marketing |
| New clients those campaigns brought in | 18 | marketing |
| Cost per new client | $3,568.16, against $2,031.81 for all campaigns in Q3 2026 | marketing, calculated |
| NM-SG's marketing costs in the ledger, Q3 2026 | $55,738.66, 43.2% over its $38,918.60 budget | finance |
| NM-SG's trading commission, Q3 2026 | $87,235.84, from **all** its clients | trading |

What it can't show is the one thing that would settle it: how much the 18 new clients have traded.
Commission is reported for the whole entity, not per client, and no agent connects a campaign's
sign-ups to their trades. So the commission figure can't show the campaign paid for itself.

An honest answer for Friday: *Nimbus Go bought 18 clients at about $3,568 each, about 76% more
than the average campaign client, in a quarter when Singapore's marketing ran 43% over budget.
Whether it was worth it depends on what those 18 clients trade, and our data can't show that
yet. Before Friday, ask the data team for commission per client, by the campaign that brought
them in.*

If your assistant says something like that, it did its job: it answered with evidence, and it
said where the evidence stops.

## Read more

- [Why evaluate agents](https://google.github.io/adk-docs/evaluate/) in the ADK docs
