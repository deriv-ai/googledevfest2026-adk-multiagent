# The marketing agent workshop

Nimbus Markets is an online broker with an AI assistant built with
[Google ADK](https://google.github.io/adk-docs/). It answers questions about **finance**,
**trading** and the day's **market news**, but not about **marketing**. Vernon, who runs
marketing, needs answers by Friday.

In one hour you build the marketing agent, plug it into the assistant, score it on hard
questions, improve it, and submit it to a competition.

## How the session runs

| Step | What you do |
|---|---|
| Set up | [Set up](#set-up), and read [the story](#the-story) while it builds |
| [Exercise 0: Meet Nimbus](exercises/0-meet-nimbus.md) | See the problem |
| [Exercise 1: Give the data a voice](exercises/1-tools.md) | Write two tools |
| [Exercise 2: Hire the marketing agent](exercises/2-agent.md) | Build the agent |
| [Exercise 3: Join the team](exercises/3-orchestrator.md) | Plug it in |
| [Exercise 4: Teamwork](exercises/4-teamwork.md) | Route questions that cross teams |
| [Exercise 5: Prove it](exercises/5-evals.md) | Score it, fix one failure, score again |
| [Submit](exercises/5-evals.md#the-competition) | Upload your `my_agent/` folder |
| Wrap up | The leaderboard, and Vernon's answer |

Each exercise ends with a check, like `make check-1`, and a link to the next one. If you fall
behind, open the hints: every exercise has one that shows the finished code.

## Before the session

Have these ready on your laptop:

- **Docker**, installed and running. [Install Docker](#install-docker) shows how.
- **`git`** and **`make`**.
- **An LLM API key** from any provider, for a model that supports tool calling. Gemini, OpenAI
  and Anthropic keys all work, as does any provider [LiteLLM](https://docs.litellm.ai/docs/providers)
  supports.
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
3. In the Ubuntu window, install `git`, `make` and `zip`:

   ```bash
   sudo apt update && sudo apt install -y git make zip
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

The practice questions were tested on `gemini/gemini-3.7-flash`. Other models score differently,
and slow ones make `make eval` slower. The competition runs everyone's agent on the same model,
so the key you use here doesn't change your competition score.

**3. Start the app.**

```bash
make up
```

The first start takes a few minutes: it downloads about 1 GB, builds the app and loads the data.
Read [the story](#the-story) while it runs.

**4. Open http://localhost:8080.** You should see the Overview page. Then start
[exercise 0](exercises/0-meet-nimbus.md).

## The story

Nimbus Markets is a fictional online broker with four companies: NM-UK, NM-SG (Singapore),
NM-AE (Dubai) and NM-INTL. Its AI assistant answers questions from the company's own data, and
finance and the trading desk use it every day.

In June, the Singapore team launched **Nimbus Go**, a new mobile app, and backed it with ad
campaigns. They spent fast. Singapore's marketing costs ran far over budget, and the CFO booked
a review for Friday with one question on the agenda: *was Nimbus Go worth the money?*

Vernon, who runs marketing, asked the assistant. It said no part of it knows about marketing.

The data team has done their part. They wrote and tested the queries over the marketing data
and left them in `my_agent/marketing_queries.py`, with a note: *"These return the right numbers.
We don't do agents. Over to you."*

You've just joined the AI team. Your job: give the assistant a marketing agent, so that by
Friday it can answer Vernon honestly.

## How the assistant works

The assistant has a main agent, an orchestrator and three specialists: finance, trading and
news. You add the fourth.

```mermaid
flowchart LR
    V([Vernon]) --> MAIN[main agent<br/>talks to people]
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
it needs, asks them, and merges what they say. Each specialist knows one part of the business and
reads only its own data. The news agent reads live headlines. No exercise uses it, but the
orchestrator still sends it news questions.

Vernon's question needs three of them at once:

```mermaid
flowchart LR
    Q["Was Nimbus Go worth it?"] --> ORCH{orchestrator}
    ORCH -->|what did it spend,<br/>who signed up?| MKT[marketing agent]
    ORCH -->|what do Singapore's<br/>clients earn us?| TRD[trading agent]
    ORCH -->|how far over budget?| FIN[finance agent]
    MKT --> A[one answer for Vernon]
    TRD --> A
    FIN --> A
```

## Where your work goes

Everything you write goes in one folder, `my_agent/`:

```
my_agent/
  marketing_agent.py      your two tools and your agent       exercises 1 and 2
  marketing_queries.py    the data team's queries; your tools call these
  team.py                 the agents the orchestrator can call    exercise 3
  prompts/
    marketing_agent.md    how your agent behaves                exercise 5
    orchestrator.md       how questions get routed              exercises 3 and 4
    main_agent.md         the assistant's persona               exercise 5
```

The rest of the app is in `platform/`. You never need to open it.

**How your changes show up.** You never restart anything. Save a file, and the app restarts
itself in about 2 seconds. Ask a question on the **Chat** page, and the **Agent route** panel
shows which agents and tools answered.

## Commands

| Command | What it does |
|---|---|
| `make up` | Start the app |
| `make check-1` | Check exercise 1 (or 0, 2, 3, 4) |
| `make eval` | Score your agents on the practice questions, in about 2 minutes |
| `make eval Q=<id>` | Score one question again |
| `make eval P=2` | Score more slowly, for a shared key or one that hits rate limits |
| `make submit NAME="<you>"` | Zip your `my_agent/` folder for the competition |
| `make logs` | Show the app's logs. Use it when something breaks |
| `make reset` | Reload the database from scratch |
| `make down` | Stop the app |

The app is at http://localhost:8080. ADK's own developer UI, with the same agents, is at
http://localhost:8000.

## If something goes wrong

| Problem | Fix |
|---|---|
| `make up` says Docker isn't running | Start Docker Desktop and wait until it says it's running. On Linux: `sudo systemctl start docker`. Then `make up` again. |
| `permission denied` on Linux | Run `sudo usermod -aG docker $USER`, log out and back in, then `make up` again. |
| `make up` stops and asks for a key | Add your key to `.env`, then `make up` again. |
| "port 5432 is already in use" | Another database is running. In `.env`, set `POSTGRES_PORT=5433`, then `make up` again. |
| The first `make up` is very slow | It downloads about 1 GB. Keep going with the story and exercise 0's reading. |
| Every chat answer is an error about the model or the key | Check `AGENT_MODEL` and `LLM_API_KEY` in `.env`, then `make up` again. If it mentions `reasoning_effort`, add `LLM_REASONING_EFFORT=` to `.env`. |
| The chat stops answering after you save a file | You have a Python error. Run `make logs`, fix it, save again. |
| On Windows, saving a file changes nothing | The repo is under `/mnt/c`. Clone it again from `cd ~` in the Ubuntu window. |
| `make eval` shows "rate limit" or many timeouts | Run `make eval P=2`. |
| The data looks wrong | Run `make reset`. |

## Going deeper

- [How the orchestrator picks agents](platform/docs/ORCHESTRATION.md)
- [How the app is built](platform/docs/ARCHITECTURE.md): containers, data model, tools and safety
- [Maintaining the app](platform/README.md): tests, data, judging, and the reference docs
