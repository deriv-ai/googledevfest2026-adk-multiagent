# The platform

This folder is the app behind the workshop: the agents, the tools, the API, the UI and the
database. Workshop participants never need to open it. Their work goes in `../my_agent/`, and the
workshop starts at the [README](../README.md) one level up.

Paths in the docs below are relative to `platform/`, except `my_agent/` and `evals/`, which are at
the repo root.

## Layout

```
src/            the agents, tools, API, exercise checks and eval runner (Python)
web/            the app's UI (React)
db/             database setup and the synthetic data (CSV)
docker/         the app image
seed/           the starter finance and trading tools
scripts/        the synthetic-data generator and the dependency patcher
tests/          the test suite
docs/           reference docs, and the facilitators' talk track
```

## Commands

Run these from the repo root with `make -C platform <target>`, or from this folder with `make`:

```bash
make test       # Python tests + UI type check
make dev        # database in a container; prints how to run the API and UI locally
make data       # regenerate the synthetic data, then run `make reset` from the repo root
make help       # list every command
```

**Security scanning** needs [trivy](https://trivy.dev). `make trivy-scan` fails on fixable
HIGH/CRITICAL issues. `make trivy-audit` patches, tests and scans in one go.

## Docs

- [docs/ORCHESTRATION.md](docs/ORCHESTRATION.md): how the orchestrator picks agents.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): containers, data model, tools and safety.
- [docs/CONTRACT.md](docs/CONTRACT.md): API, settings, database schema and eval format.
- [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md): talk track for the presenters. It contains answers,
  so don't point participants at it.

## Notes

**The hidden competition set** is `evals/final.enc` at the repo root. The readable
`evals/final.yaml` is gitignored and stays with the facilitators. After editing it, encrypt it
again from this folder:

```bash
uv run python -m devfest_agents.evals ../evals/final.yaml --encrypt --key "<passphrase>"
```

**All data is synthetic.** `scripts/generate_synthetic_data.py` generates every client, trade,
ledger line and campaign.

**`cryptography` is held below version 47** in `pyproject.toml`. Newer versions crash with
"Illegal instruction" inside Podman on Apple Silicon Macs.
