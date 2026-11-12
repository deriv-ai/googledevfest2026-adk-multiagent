"""Score competition submissions and keep a leaderboard (facilitators only).

    python -m devfest_agents.judge submissions.csv --questions ../evals/final.yaml

Each submission is a fork and a commit. For each one the judge:

1. fetches only `my_agent/` from that commit (the rest of the fork is ignored),
2. starts the app image with that folder mounted, on the running stack's network,
   so it shares the database and the news server,
3. asks every question through the app's chat API and grades the answers here,
   outside the participant's code, so their code can't touch the grading,
4. saves the result and rewrites leaderboard.html.

Results are cached per commit: run the judge again and it only scores new commits.
The participant's code runs with the LLM key from --env-file, so use a key with a
spending cap.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import re
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import httpx

from . import evals
from .config import PLATFORM_ROOT, REPO_ROOT
from .leaderboard import write_leaderboard

BOOT_TIMEOUT_S = 90
APP_CONTAINER = "nimbus-app"  # the running stack's app; submissions copy its settings
STACK_KEYS = ("DATABASE_URL", "AGENT_DATABASE_URL", "NEWS_MCP_URL", "STATIC_DIR", "STARTER_TOOLS_PATH")


@dataclass
class Submission:
    name: str
    repo: str
    commit: str = ""          # empty: the default branch's latest commit
    submitted_at: str = ""


class JudgeError(Exception):
    """This submission can't be scored; the message says why."""


# ---------------------------------------------------------------------------
# Submissions
# ---------------------------------------------------------------------------
def read_submissions(path: Path) -> list[Submission]:
    """A CSV with name and repo columns, and optionally commit and a timestamp.
    Header names are matched loosely, so a form export works as it is. When a name
    appears more than once, the last row counts: your latest submission is the one judged."""
    with path.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    def pick(row: dict[str, str], *words: str) -> str:
        for key, value in row.items():
            if key and any(word in key.lower() for word in words):
                return (value or "").strip()
        return ""

    subs = [Submission(name=pick(row, "name", "team"), repo=https_url(pick(row, "repo", "fork", "url")),
                       commit=pick(row, "commit"), submitted_at=pick(row, "timestamp", "submitted", "time"))
            for row in rows]
    latest = {slug(s.name): s for s in subs if s.name and s.repo}
    return list(latest.values())


def https_url(repo: str) -> str:
    """git@github.com:me/fork.git -> https://github.com/me/fork.git, so no SSH key is needed."""
    match = re.fullmatch(r"git@([^:]+):(.+)", repo)
    return f"https://{match[1]}/{match[2]}" if match else repo


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "anonymous"


# ---------------------------------------------------------------------------
# Running one submission
# ---------------------------------------------------------------------------
async def sh(*args: str, check: bool = True) -> str:
    proc = await asyncio.create_subprocess_exec(*args, stdout=asyncio.subprocess.PIPE,
                                                stderr=asyncio.subprocess.STDOUT)
    out = (await proc.communicate())[0].decode(errors="replace").strip()
    if check and proc.returncode != 0:
        raise JudgeError(f"`{' '.join(args[:3])} ...` failed: {out[-300:]}")
    return out


async def fetch_my_agent(sub: Submission, workdir: Path) -> tuple[Path, str]:
    """Check out my_agent/ at the submitted commit. Returns its path and the full commit id."""
    repo = workdir / "repo"
    if not repo.exists():
        await sh("git", "clone", "--quiet", "--no-checkout", "--filter=blob:none", sub.repo, str(repo))
    else:
        await sh("git", "-C", str(repo), "fetch", "--quiet", "origin")
    wanted = sub.commit or "origin/HEAD"
    try:
        commit = await sh("git", "-C", str(repo), "rev-parse", "--verify", f"{wanted}^{{commit}}")
    except JudgeError:
        raise JudgeError(f"commit {wanted[:12]} isn't on the fork. Was it pushed?") from None
    await sh("git", "-C", str(repo), "checkout", "--quiet", "--force", commit, "--", "my_agent")
    my_agent = repo / "my_agent"
    if not (my_agent / "team.py").exists():
        raise JudgeError("that commit has no my_agent/team.py")
    return my_agent, commit


async def stack_settings(args: argparse.Namespace) -> list[str]:
    """The database and news-server settings of the running app, as -e flags, so every
    submission talks to the same stack the same way."""
    raw = await sh(args.engine, "inspect", APP_CONTAINER, "--format", "{{json .Config.Env}}", check=False)
    try:
        env = dict(item.split("=", 1) for item in json.loads(raw))
    except (json.JSONDecodeError, TypeError, ValueError):
        raise JudgeError(f"can't read the settings of {APP_CONTAINER}. Start the stack first: make up") from None
    return [flag for key in STACK_KEYS if key in env for flag in ("-e", f"{key}={env[key]}")]


async def start_app(args: argparse.Namespace, name: str, my_agent: Path, settings: list[str]) -> str:
    """Start the app with this my_agent/ mounted. Returns its base URL."""
    await sh(args.engine, "rm", "-f", name, check=False)
    await sh(args.engine, "run", "-d", "--name", name, "--network", args.network, "-p", "127.0.0.1::8080",
             "--env-file", str(args.env_file), *settings, "-e", "LOG_LEVEL=WARNING",
             "-v", f"{my_agent.resolve()}:/app/my_agent:ro", args.image)
    port = (await sh(args.engine, "port", name, "8080/tcp")).splitlines()[0].rsplit(":", 1)[1]
    url = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + BOOT_TIMEOUT_S
    async with httpx.AsyncClient(timeout=3) as client:
        while time.monotonic() < deadline:
            try:
                if (await client.get(f"{url}/api/health")).status_code == 200:
                    return url
            except httpx.HTTPError:
                pass
            await asyncio.sleep(1)
    logs = await sh(args.engine, "logs", "--tail", "15", name, check=False)
    raise JudgeError(f"the app didn't start within {BOOT_TIMEOUT_S} s. Last log lines:\n{logs}")


def sse_events(lines) -> list[dict[str, Any]]:
    """The events in server-sent-event lines; keepalive comments and blank lines are skipped."""
    return [json.loads(line[6:]) for line in lines if line.startswith("data: ")]


def http_asker(url: str):
    """Ask one question through POST /api/chat and collect the streamed events."""

    async def ask(question: dict[str, Any]) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        body = {"conversation_id": f"judge-{question['id']}", "message": question["question"]}
        try:
            async with httpx.AsyncClient(timeout=None) as client, \
                    client.stream("POST", f"{url}/api/chat", json=body) as response:
                async for line in response.aiter_lines():
                    events.extend(sse_events([line]))
        except httpx.HTTPError as exc:
            events.append({"type": "error", "message": f"{type(exc).__name__}: {exc}"})
        return events or [{"type": "error", "message": "the app sent no events"}]

    return ask


async def judge_one(args: argparse.Namespace, sub: Submission, questions: list[dict[str, Any]]) -> dict[str, Any]:
    workdir = args.out / "work" / slug(sub.name)
    workdir.mkdir(parents=True, exist_ok=True)
    result: dict[str, Any] = asdict(sub) | {"score": 0, "max_score": 2 * len(questions), "by_kind": {},
                                            "error": None, "judged_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    container = f"judge-{slug(sub.name)}"
    try:
        my_agent, result["commit"] = await fetch_my_agent(sub, workdir)
        cached = args.out / "results" / f"{slug(sub.name)}-{result['commit'][:12]}.json"
        if cached.exists() and not args.force:
            return json.loads(cached.read_text())
        url = await start_app(args, container, my_agent, args.stack_settings)
        report = await evals.run(questions, http_asker(url), parallel=args.parallel, timeout_s=args.timeout,
                                 hidden=True, quiet=True)
        result |= {"score": report["score"], "by_kind": points_by_kind(report["results"]),
                   "error": shared_error(report["results"])}
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_text(json.dumps(result, indent=2))
    except JudgeError as exc:
        result["error"] = str(exc)
    finally:
        await sh(args.engine, "rm", "-f", container, check=False)
    return result


def points_by_kind(results: list[dict[str, Any]]) -> dict[str, list[int]]:
    by_kind: dict[str, list[int]] = {}
    for r in results:
        points = by_kind.setdefault(r["kind"] or "other", [0, 0])
        points[0] += r["route_point"] + r["answer_point"]
        points[1] += 2
    return by_kind


def shared_error(results: list[dict[str, Any]]) -> str | None:
    """When every question failed the same way (say, the agents don't build), report that once."""
    errors = {r["error"] for r in results}
    return next(iter(errors)) if len(errors) == 1 and None not in errors else None


# ---------------------------------------------------------------------------
# All submissions
# ---------------------------------------------------------------------------
def saved_results(out: Path) -> dict[str, dict[str, Any]]:
    """Every result judged so far, the most recently judged one per name."""
    board: dict[str, dict[str, Any]] = {}
    for path in sorted((out / "results").glob("*.json"), key=lambda p: p.stat().st_mtime):
        result = json.loads(path.read_text())
        board[slug(result["name"])] = result
    return board


async def judge_all(args: argparse.Namespace) -> None:
    subs = read_submissions(args.submissions)
    questions = evals.load_questions(args.questions)
    if not subs:
        raise JudgeError(f"no submissions with a name and a repo in {args.submissions}")
    networks = await sh(args.engine, "network", "ls", "--format", "{{.Name}}")
    if args.network not in networks.split():
        raise JudgeError(f"network {args.network} doesn't exist. Start the stack first: make up")
    args.stack_settings = await stack_settings(args)

    evals.log(f"Judging {len(subs)} submission(s) on {len(questions)} questions, {args.at_once} at a time...")
    gate = asyncio.Semaphore(args.at_once)
    board = saved_results(args.out)  # name -> result; earlier runs stay on the board

    async def one(sub: Submission) -> None:
        async with gate:
            started = time.monotonic()
            result = await judge_one(args, sub, questions)
        board[slug(sub.name)] = result
        write_leaderboard(list(board.values()), args.out)
        note = f"  ({result['error'].splitlines()[0][:80]})" if result["error"] else ""
        evals.log(f"  {result['score']:>3}/{result['max_score']}  {sub.name}  "
                  f"[{time.monotonic() - started:.0f} s]{note}")

    await asyncio.gather(*(one(s) for s in subs))
    evals.log(f"\nLeaderboard: {(args.out / 'leaderboard.html').resolve()}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Score competition submissions into a leaderboard.")
    parser.add_argument("submissions", type=Path, help="CSV with name, repo and optionally commit and timestamp")
    parser.add_argument("--questions", type=Path, default=REPO_ROOT / "evals" / "final.yaml")
    parser.add_argument("--out", type=Path, default=PLATFORM_ROOT / ".judge", help="results and leaderboard.html")
    parser.add_argument("--engine", default="docker", help="docker or podman")
    parser.add_argument("--image", default="nimbus-app:latest")
    parser.add_argument("--network", default="nimbus-adk_default", help="the running stack's network")
    parser.add_argument("--env-file", type=Path, default=REPO_ROOT / ".env", help="LLM key for the submissions")
    parser.add_argument("--at-once", type=int, default=2, help="submissions to score at the same time")
    parser.add_argument("--parallel", type=int, default=evals.PARALLEL, help="questions at the same time, each")
    parser.add_argument("--timeout", type=float, default=evals.TIMEOUT_S, help="seconds per question")
    parser.add_argument("--force", action="store_true", help="score again even if a commit was scored before")
    args = parser.parse_args()
    try:
        asyncio.run(judge_all(args))
    except (JudgeError, evals.EvalSetupError) as exc:
        evals.log(f"{evals.NO} {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
