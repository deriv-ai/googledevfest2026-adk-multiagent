# Exercise 1: Creating tools

[Back to the workshop](../README.md) · [Previous: Exploring the app](0-explore.md)
## The problem

The query functions work, but a model can't use them well. They have names like
`fetch_campaign_performance` and a one-line comment for developers. Nothing tells Gemini what
they return, when to call them, or what format the dates need.

Your job is to wrap them as **tools**: functions written for a model to read.

## What helps

In ADK, a tool can be a plain Python function. ADK reads three things from it and turns them
into a description that Gemini sees:

- the **function name**, which becomes the tool's name;
- the **type hints**, which become its parameters, and a default makes a parameter optional;
- the **docstring**, which becomes its description. This is the important one. The docstring is
  the prompt for the tool.

Here's a tool from a different world:

```python
async def get_forecast(city: str, days: int = 3) -> dict:
    """Weather forecast for a city, one row per day.

    Use it when someone asks about the weather, or what to pack for a trip.

    Args:
        city: City name, e.g. "Kuala Lumpur".
        days: How many days ahead, 1 to 7.
    """
    return await weather_api.forecast(city, days)
```

The model never sees the body. It decides whether to call `get_forecast`, and with which
arguments, from the name, the hints and the docstring alone. A good docstring says what comes
back, when to use the tool, and what each argument looks like.

## Your task

Open **`my_agent/marketing_agent.py`** and find the comment `# Exercise 1`.
Write **two tools** there:

1. one that shows how each **campaign** did over a date range;
2. one that shows how each **ad channel** did over a date range.

Each tool calls one of the queries and returns its result. `marketing_queries.py` is already
imported as `queries`.

Further down the file are three **ready-made tools** that wrap the other queries, so
you don't have to type them all. Read one first: yours follow the same pattern.

Put real effort into the docstrings. Later, a model that has never seen this code will pick
between all five tools using only what's written there.

<details>
<summary>Hint: which queries?</summary>

`queries.fetch_campaign_performance(...)` and `queries.fetch_channel_summary(...)`. Their
signatures are in `my_agent/marketing_queries.py`.

</details>

<details>
<summary>Hint: what goes in the docstring?</summary>

Look at what the query returns: open the Data Schema page, or call the tool once and look at the
rows in the route panel later. Then write:

- one line on what the tool returns;
- the columns, with units (`spend_usd` is US dollars);
- an example question it answers;
- the format of every argument, especially dates (`YYYY-MM-DD`) and entity ids (`NM-UK`, `NM-SG`,
  `NM-AE`, `NM-INTL`).

</details>

<details>
<summary>Hint: show me one finished tool</summary>

```python
async def campaign_performance(start_date: str, end_date: str, entity_id: str | None = None) -> dict:
    """Spend, clicks and sign-ups per campaign for a date range.

    One row per campaign: campaign_id, name, entity_id, channel, spend_usd, impressions,
    clicks, signups (new clients the campaign brought in) and cost_per_signup_usd.
    Use it for "how did our campaigns do last quarter?" or "how did the Nimbus Go campaigns do?".

    Args:
        start_date: First day, YYYY-MM-DD.
        end_date: Last day (inclusive), YYYY-MM-DD.
        entity_id: Only campaigns of this entity: NM-UK, NM-SG, NM-AE or NM-INTL. Omit for all.
    """
    return await queries.fetch_campaign_performance(start_date, end_date, entity_id)
```

The channel tool follows the same pattern with `queries.fetch_channel_summary`.

</details>

## Check it

```bash
make check-1
```

It finds the two tools you wrote, checks their docstrings and type hints, asks ADK to turn each
one into a tool, and runs each against the real data.

Nothing changes in the app yet. Your tools have no agent to use them until exercise 2, and nobody
calls that agent until exercise 3. The check is how you know you're on track.

## Read more

- [Function tools](https://google.github.io/adk-docs/tools/function-tools/) in the ADK docs

## Next

You have two good tools and nobody to use them. In **[exercise 2](2-agent.md)** you hire the
agent.
