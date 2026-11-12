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
news_mcp/       the news agent's MCP server (live RSS headlines)
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
make dev        # database and news server in containers; prints how to run the API and UI locally
make data       # regenerate the synthetic data, then run `make reset` from the repo root
make help       # list every command
```

**Security scanning** needs [trivy](https://trivy.dev). `make trivy-scan` fails on fixable
HIGH/CRITICAL issues. `make trivy-audit` patches, tests and scans in one go.

## Docs

- [docs/ORCHESTRATION.md](docs/ORCHESTRATION.md): how the orchestrator picks agents.
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): containers, data model, tools and safety.
- [docs/CONTRACT.md](docs/CONTRACT.md): API, settings, database schema and eval format.
- [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md): the 60-minute plan and talk track for the presenters.
  It contains answers, so don't point participants at it.
- [docs/CHALLENGES.md](docs/CHALLENGES.md): what separates finishing the exercises from full marks,
  and what the reference solutions (branches `solution-guided` and `solution-improved`) score.

## Notes

**Judging the competition.** The hidden set is `evals/final.yaml` at the repo root. It's
gitignored, so it only exists on the facilitators' machines.

1. Make a Google Drive folder that anyone with the link can upload to, and share the link.
   Participants run `make submit NAME="<name>"` and upload the zip it makes.
2. Download the Drive folder (Drive gives you a zip), and with the stack running (`make up`),
   score it. The judge takes the zip or the unzipped folder:

   ```bash
   make -C platform judge SUBMISSIONS=~/Downloads/submissions.zip
   ```

3. Open `platform/.judge/leaderboard.html` on the projector. It refreshes every 15 seconds.

Each `<name>.zip` or `<name>/` folder is one submission, named after the file. A second upload
under the same name (Drive downloads it as `<name> (1).zip`) replaces the first; on a tie, the
earlier upload wins, going by the files' modified times.

**Fit judging into the hour.** Each submission takes about 2 minutes to score (22 questions, 8
at a time). With 30 participants and 2 at a time, that's 30 minutes, which is too long for the
6 minutes after the deadline. So start at 0:45, as soon as the first uploads arrive, and
download and re-run every few minutes. Raise `--at-once` to 4 or 6 if your key's rate limit
allows it.

Re-run the same command on a fresh download at any time: uploads already scored are skipped.
Pass options through `JUDGE_ARGS`, for example `JUDGE_ARGS="--at-once 4"` to score four
submissions at a time, or `--force` to score everything again. The participants' code runs with
the LLM key in `.env`, so use a key with a spending cap. A participant's code also runs with the
app's database role, so look over the top few `my_agent/` folders before you announce winners.

**All data is synthetic.** `scripts/generate_synthetic_data.py` generates every client, trade,
ledger line and campaign.

**`cryptography` is held below version 47** in `pyproject.toml`. Newer versions crash with
"Illegal instruction" inside Podman on Apple Silicon Macs.
