# The marketing agent workshop

Nimbus Markets is a fictional online broker with an AI assistant built with
[Google ADK](https://google.github.io/adk-docs/). It answers questions about **finance**,
**trading** and the day's **market news**, but not about **marketing**.

Your task is to add a marketing agent, connect it to the assistant, and measure how well it
answers. At the end you run your agent on questions you haven't seen, and hand in its answers.
[The task](#the-task) has the details.

## How the session runs

| Step | What you do |
|---|---|
| Set up | [Set up](#set-up), and read [the task](#the-task) while it builds |
| [Exercise 0: Exploring the app](exercises/0-explore.md) | See what the assistant can't answer yet |
| [Exercise 1: Creating tools](exercises/1-tools.md) | Wrap two marketing queries as tools |
| [Exercise 2: Creating an agent](exercises/2-agent.md) | Give the tools to a marketing agent |
| [Exercise 3: Adding an agent to the orchestrator](exercises/3-orchestrator.md) | Let the orchestrator send marketing questions to it |
| [Exercise 4: Routing across agents](exercises/4-routing.md) | Ask several agents, in parallel or in order. **On your own**, about 8 minutes |
| [The competition](exercises/5-competition.md) | Practise with `make eval`, then answer the secret questions and upload the answers |
| Wrap up | The top 3, and the winner's answer to the final question |

The session is 60 minutes: about 10 minutes of slides, 35 minutes of building, and 15 minutes for
the competition. The facilitators introduce each exercise in a minute or two, then you build it.
Each exercise ends with a check, like `make check-1`, and a link to the next one.

## Before the session

Have these ready on your laptop:

- **Docker**, installed and running. [Install Docker](#install-docker) shows how.
- **`git`** and **`make`**.
- **The app built already.** The first `make up` downloads about 1 GB, which venue Wi-Fi can't do
  for a whole room. Before you come, do [Set up](#set-up) steps 1 to 3 with
  `LLM_API_KEY=later` in `.env`: any text works until you have your real key.
- **An LLM key.** At the session, scan the QR code on the slides to claim a key with a $5
  limit. It pays for everything you run today. Put it in `.env` and run `make up` again.
- **Some Python.** You'll write two short `async def` functions with type hints and docstrings,
  and fill in one function call. You don't need Python installed: everything runs in Docker.

### Install Docker

**macOS.** Install [Docker Desktop for Mac](https://docs.docker.com/desktop/setup/install/mac-install/)
and open it. For `git` and `make`, run:

```bash
xcode-select --install
```

**Windows.** You'll work inside WSL, the Linux that comes with Windows.

1. Open PowerShell as administrator, run `wsl --install`, and restart. Then open **Ubuntu** from
   the Start menu and choose a username and password.
2. Install [Docker Desktop for Windows](https://docs.docker.com/desktop/setup/install/windows-install/).
   In its settings, under **Resources > WSL integration**, turn on Ubuntu.
3. In the Ubuntu window, install `git` and `make`:

   ```bash
   sudo apt update && sudo apt install -y git make
   ```

Run every command in this workshop in the Ubuntu window. Clone the repo into your Linux home
folder (`cd ~` first), not under `/mnt/c`: from there, the app doesn't see the files you save.

**Linux.** Install [Docker Engine](https://docs.docker.com/engine/install/) with the Compose
plugin, then let your user run Docker without `sudo`, and log out and back in:

```bash
sudo usermod -aG docker $USER
```

Install `git` and `make` with your package manager.

**Check it works.** Both of these should succeed:

```bash
docker run --rm hello-world
```

```bash
docker compose version
```

## Set up

**1. Get the code.**

```bash
git clone <this repo's URL>
cd googledevfest2026-adk-multiagent
```

**2. Add your key.** Copy the settings file:

```bash
cp .env.example .env
```

Then open `.env` and fill in two lines:

```bash
LLM_API_KEY=<your key>
AGENT_MODEL=<provider>/<model>
```

`AGENT_MODEL` is the provider, a slash and the model, for example `gemini/gemini-3.7-flash` or
`anthropic/claude-sonnet-5-5`. [LiteLLM's provider list](https://docs.litellm.ai/docs/providers)
has the names for the others. If your key is for an OpenAI-compatible endpoint, such as a LiteLLM
proxy or OpenRouter, also set `LLM_BASE_URL=<its URL>` and use `openai/<model>`.

The exercises were tested on `gemini/gemini-3.7-flash`. Use the key from the session's QR code,
and the model it comes with: your agent answers the competition's questions on that key, which
has a $5 limit, and your answers file records the model. If you set up before the session with
`LLM_API_KEY=later`, put the real key in now and run `make up` again.

**3. Start the app.**

```bash
make up
```

The first start takes a few minutes: it downloads about 1 GB, builds the app and loads the data.
Read [the task](#the-task) while it runs.

**4. Open http://localhost:8080.** You should see the Overview page. Then start
[exercise 0](exercises/0-explore.md).

## The task

**Background.** Nimbus Markets has four companies: NM-UK, NM-SG (Singapore), NM-AE (Dubai) and
NM-INTL. In June 2026, NM-SG launched a mobile app, **Nimbus Go**, with paid ad campaigns. The
database holds the marketing data: campaigns, daily ad spend and sign-ups. No agent reads it yet.

**What you're given:**

- a working assistant with a main agent, an orchestrator and three specialists: finance, trading
  and news;
- `my_agent/marketing_queries.py`, tested queries over the marketing data, as Python functions;
- a starter `my_agent/` folder and a check for each exercise.

**What you build:**

1. tools that wrap the marketing queries;
2. a marketing agent that uses them;
3. the routing that sends marketing questions to it, alone or together with the other agents.

**How it's scored.** Every question is worth 5 marks: 1 for asking the right agents, and 4 from an
LLM judge that checks the answer against 4 criteria, such as the right figures and the figures
behind them. The final question is *"Was the Nimbus Go launch campaign worth the money?"* A good
answer gives the figures and says what the data can't show.

**What you hand in.** Your agent's answers to the secret questions: `make eval-final` writes them
to `evals/submission.json`, and you upload that file to the competition's form.

## How the assistant works

The assistant has a main agent, an orchestrator and three specialists: finance, trading and news.
You add the fourth.

```mermaid
flowchart LR
    U([you]) --> MAIN[main agent<br/>talks to people]
    MAIN --> ORCH{orchestrator<br/>picks the specialists}
    ORCH --> FIN[finance agent]
    ORCH --> TRD[trading agent]
    ORCH --> NEWS[news agent]
    ORCH -.-> MKT[marketing agent<br/>you build this]
    FIN --> FDB[(finance data)]
    TRD --> TDB[(trading data)]
    NEWS --> WEB[(live headlines)]
    MKT -.-> MDB[(marketing data)]

    classDef new stroke-dasharray: 5 5
    class MKT,MDB new
```

The main agent talks to people. The orchestrator reads each question, decides which specialists
it needs, asks them, and merges what they say. Each specialist reads only its own data.

## Where your work goes

Everything you write goes in one folder, `my_agent/`:

```
my_agent/
  marketing_agent.py      your two tools and your agent       exercises 1 and 2
  marketing_queries.py    the marketing queries; your tools call these
  team.py                 the agents the orchestrator can call    exercise 3
  prompts/
    marketing_agent.md    how your agent behaves
    orchestrator.md       how questions get routed              exercises 3 and 4
    main_agent.md         the assistant's persona
```

The rest of the app is in `platform/`. You never need to edit it.

**How your changes show up.** You never restart anything. Save a file, and the app restarts
itself in about 2 seconds. Ask a question on the **Chat** page, and the **Agent route** panel
shows which agents and tools answered.

## Commands

| Command | What it does |
|---|---|
| `make up` | Start the app |
| `make check-1` | Check exercise 1 (or 0, 2, 3) |
| `make eval` | Score your agent on the 5 practice questions |
| `make eval-final KEY=... NAME="<you>"` | Answer the competition questions and write your answers file |
| `make logs` | Show the app's logs. Use it when something breaks |
| `make reset` | Reload the database from scratch |
| `make down` | Stop the app |

The app is at http://localhost:8080. ADK's own developer UI, with the same agents, is at
http://localhost:8000.
