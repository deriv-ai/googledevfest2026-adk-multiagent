# Build a marketing agent with Google ADK

Nimbus Markets is an online broker. It has an AI assistant built with
[Google ADK](https://google.github.io/adk-docs/) that answers questions about **finance** and
**trading**. It cannot answer questions about **marketing**, and Vernon, who runs marketing,
needs answers by Friday.

In this workshop you build the marketing agent and plug it into the assistant. Then you score your
agent on a set of hard questions, and compete for the best score.

**The workshop is in [WORKSHOP.md](WORKSHOP.md).** This page only gets the app running.

---

## Setup

You need:

- Docker (with Compose)
- `make` and `git`
- a free Gemini API key from [Google AI Studio](https://aistudio.google.com/apikey)

Then run these steps.

**1. Get the code.** Fork this repo on GitHub, then clone your fork:

```bash
git clone <your fork's URL>
cd devfest_adk_multiagent
```

**2. Create your settings file.**

```bash
cp .env.example .env
```

**3. Add your key.** Open `.env` and paste your key after `GEMINI_API_KEY=`.

**4. Start the app.**

```bash
make up
```

The first start takes a few minutes. It builds the app and loads the data.

**5. Open http://localhost:8080.** You should see the Overview page.

Now go to **[WORKSHOP.md](WORKSHOP.md)**.

---

## What is running

| Address | What it is |
|---|---|
| http://localhost:8080 | The app: chat, live agent route, tools, data schema |
| http://localhost:8000 | ADK's own developer UI, showing the same agents |
| `localhost:5432` | The Postgres database (user `postgres`, password `postgres`, database `nimbus`) |

Everything runs on your machine only.

---

## How the system works

```
You ──> main_agent ──> orchestrator ──> finance_agent    reads the finance tables
                                    ├─> trading_agent    reads the trading tables
                                    └─> marketing_agent  reads the marketing tables  <- you build this
```

- **main_agent** talks to you. It passes every business question to the orchestrator.
- **orchestrator** picks which agents a question needs. It calls them and merges their answers.
- **finance_agent** and **trading_agent** already exist.
- **marketing_agent** is what you add in the workshop.

When you save a Python file, the app reloads by itself. You never need to restart it.

---

## Useful commands

| Command | What it does |
|---|---|
| `make up` | Start everything |
| `make check-1` | Check exercise 1 (or 0, 2, 3, 4) |
| `make eval` | Score your agents on the practice questions |
| `make eval-final KEY=...` | Score your agents on the hidden competition questions |
| `make logs` | Show the logs. Use it when something breaks. |
| `make reset` | Wipe the database and load the data again |
| `make down` | Stop everything |

---

## If something goes wrong

| Problem | Fix |
|---|---|
| `make up` stops and asks for a key | Add your key to `.env`, then run it again. |
| "port 5432 is already in use" | Another database is running. In `.env`, change `POSTGRES_PORT=5432` to `POSTGRES_PORT=5433`, then start again. |
| The chat stops answering after you save a file | You have a Python error. Run `make logs`, fix the error, save again. |
| The data looks wrong | Run `make reset`. |

To use a LiteLLM proxy instead of a Gemini key, set `LITELLM_GEMINI_API_KEY` and `OPENAI_BASE_URL`
in `.env`. The comments in `.env.example` explain both options.

---

## More docs

- [WORKSHOP.md](WORKSHOP.md): the workshop. **Start here.**
- [docs/ORCHESTRATION.md](docs/ORCHESTRATION.md): how the orchestrator picks agents.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): containers, data model, tools and safety.
- [docs/CONTRACT.md](docs/CONTRACT.md): API, settings, database schema and eval format.
- [docs/EXTRA_UI_TOOLS.md](docs/EXTRA_UI_TOOLS.md): extra exercise, add finance and trading tools from the UI.
- [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md): talk track for the presenters.

---

## For maintainers

**Repo layout**

```
WORKSHOP.md     the workshop: story, architecture, exercise list
exercises/      one file per exercise
src/            the agents, tools, API and eval runner (Python)
web/            the app's UI (React)
db/             database setup and the synthetic data (CSV)
evals/          practice questions, and the encrypted competition set
seed/           the starter finance and trading tools
scripts/        the synthetic-data generator
tests/          the test suite
docs/           detailed docs
```

**Other commands**

```bash
make test       # Python tests + UI type check
make dev        # database in a container; prints how to run the API and UI locally
make data       # regenerate the synthetic data, then run `make reset` to load it
make help       # list every command
```

**Security scanning** needs [trivy](https://trivy.dev). `make trivy-scan` fails on fixable
HIGH/CRITICAL issues. `make trivy-audit` patches, tests and scans in one go. Run `make help` for
the rest.

**The hidden competition set** is `evals/final.enc`. The readable `evals/final.yaml` is
gitignored and stays with the facilitators. After editing it, encrypt it again:

```bash
uv run python -m devfest_agents.evals evals/final.yaml --encrypt --key "<passphrase>"
```

**All data is synthetic.** `scripts/generate_synthetic_data.py` generates every client, trade,
ledger line and campaign.

**Note:** `cryptography` is held below version 47 in `pyproject.toml`. Newer versions crash with
"Illegal instruction" inside Podman on Apple Silicon Macs.
