"""Score competition submissions and keep a leaderboard (facilitators only).

    python -m devfest_agents.judge ~/Downloads/submissions --questions ../evals/final.yaml

Participants upload their `my_agent/` folder, zipped by `make submit` and named after
them, to a shared Google Drive folder. Download that folder and point the judge at it
(the folder, or the zip Google Drive gives you). Each `<name>.zip` or `<name>/` inside
is one submission. For each one the judge:

1. unpacks its `my_agent/` (the folder that holds team.py),
2. starts the app image with that folder mounted, on the running stack's network,
   so it shares the database and the news server,
3. asks every question through the app's chat API and grades the answers here,
   outside the participant's code, so their code can't touch the grading,
4. saves the result and rewrites leaderboard.html.

Results are cached per version (a hash of the files): run the judge again and it only
scores new or changed uploads. The participant's code runs with the LLM key from
--env-file, so use a key with a spending cap.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import shutil
import sys
import time
import zipfile
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
SKIP = {"__pycache__", ".DS_Store", "__MACOSX"}  # junk that zips and Macs add


@dataclass
class Submission:
    name: str
    path: Path               # a .zip or a folder
    submitted_at: str = ""   # the upload's modified time, for tie-breaks


class JudgeError(Exception):
    """This submission can't be scored; the message says why."""


# ---------------------------------------------------------------------------
# Submissions
# ---------------------------------------------------------------------------
def read_submissions(inbox: Path, out: Path) -> list[Submission]:
    """One submission per `<name>.zip` or `<name>/` in the inbox. A zip of the whole
    inbox (what Google Drive's "Download" gives you) is unpacked first. When two uploads
    share a name (Drive downloads the second as "Ada (1).zip"), the newer one counts."""
    if inbox.is_file() and inbox.suffix == ".zip":
        unpacked = out / "inbox"
        shutil.rmtree(unpacked, ignore_errors=True)
        unzip(inbox, unpacked)
        inbox = unpacked
    if not inbox.is_dir():
        raise JudgeError(f"{inbox} isn't a folder or a .zip")
    entries = [p for p in inbox.iterdir() if p.name not in SKIP and not p.name.startswith(".")
               and (p.is_dir() or p.suffix == ".zip")]
    # Drive wraps a downloaded folder in one more folder of the same name; look inside it.
    if len(entries) == 1 and entries[0].is_dir() and not find_my_agent(entries[0], depth=1):
        return read_submissions(entries[0], out)
    latest: dict[str, Submission] = {}
    for path in sorted(entries, key=lambda p: p.stat().st_mtime):
        name = path.stem if path.suffix == ".zip" else path.name
        name = re.sub(r"\s*\(\d+\)$", "", name)  # "Ada (1)": Drive's name for a second upload
        latest[slug(name)] = Submission(name=name, path=path, submitted_at=time.strftime(
            "%Y-%m-%d %H:%M:%S", time.localtime(path.stat().st_mtime)))
    return list(latest.values())


def unzip(archive: Path, dest: Path) -> None:
    """Extract a zip, refusing any entry that would land outside dest."""
    dest.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(archive) as zf:
            for member in zf.namelist():
                if not (dest / member).resolve().is_relative_to(dest.resolve()):
                    raise JudgeError(f"{archive.name} has a file outside its own folder: {member}")
            zf.extractall(dest)
    except zipfile.BadZipFile:
        raise JudgeError(f"{archive.name} isn't a readable zip") from None


def find_my_agent(root: Path, depth: int = 3) -> Path | None:
    """The shallowest folder under root that holds team.py."""
    level = [root]
    for _ in range(depth + 1):
        for folder in level:
            if (folder / "team.py").is_file():
                return folder
        level = [c for f in level for c in sorted(f.iterdir()) if c.is_dir() and c.name not in SKIP]
    return None


def files_of(folder: Path) -> list[Path]:
    return sorted(p for p in folder.rglob("*")
                  if p.is_file() and not SKIP & set(p.relative_to(folder).parts) and p.suffix != ".pyc")


def version(folder: Path) -> str:
    """A hash of every file's path and contents, so an unchanged upload isn't scored twice."""
    digest = hashlib.sha256()
    for path in files_of(folder):
        digest.update(path.relative_to(folder).as_posix().encode() + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()


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


def unpack_my_agent(sub: Submission, workdir: Path) -> tuple[Path, str]:
    """Copy the submission's my_agent/ into workdir. Returns its path and its version."""
    shutil.rmtree(workdir, ignore_errors=True)
    source = workdir / "upload"
    if sub.path.is_dir():
        shutil.copytree(sub.path, source)
    else:
        unzip(sub.path, source)
    found = find_my_agent(source)
    if found is None:
        raise JudgeError("no team.py inside. Upload the whole my_agent folder (make submit zips it).")
    my_agent = workdir / "my_agent"
    shutil.copytree(found, my_agent, ignore=shutil.ignore_patterns(*SKIP, "*.pyc"))
    return my_agent, version(my_agent)


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
    result: dict[str, Any] = asdict(sub) | {"path": str(sub.path), "version": "", "score": 0, "max_score": 2 * len(questions), "by_kind": {},
                                            "error": None, "judged_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    container = f"judge-{slug(sub.name)}"
    try:
        my_agent, result["version"] = unpack_my_agent(sub, workdir)
        cached = args.out / "results" / f"{slug(sub.name)}-{result['version'][:12]}.json"
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
    subs = read_submissions(args.submissions, args.out)
    questions = evals.load_questions(args.questions)
    if not subs:
        raise JudgeError(f"no .zip files or folders in {args.submissions}")
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
    parser.add_argument("submissions", type=Path, help="the downloaded Drive folder (or its .zip): one <name>.zip or <name>/ per submission")
    parser.add_argument("--questions", type=Path, default=REPO_ROOT / "evals" / "final.yaml")
    parser.add_argument("--out", type=Path, default=PLATFORM_ROOT / ".judge", help="results and leaderboard.html")
    parser.add_argument("--engine", default="docker", help="docker or podman")
    parser.add_argument("--image", default="nimbus-app:latest")
    parser.add_argument("--network", default="nimbus-adk_default", help="the running stack's network")
    parser.add_argument("--env-file", type=Path, default=REPO_ROOT / ".env", help="LLM key for the submissions")
    parser.add_argument("--at-once", type=int, default=2, help="submissions to score at the same time")
    parser.add_argument("--parallel", type=int, default=evals.PARALLEL, help="questions at the same time, each")
    parser.add_argument("--timeout", type=float, default=evals.TIMEOUT_S, help="seconds per question")
    parser.add_argument("--force", action="store_true", help="score again even if a version was scored before")
    args = parser.parse_args()
    try:
        asyncio.run(judge_all(args))
    except (JudgeError, evals.EvalSetupError) as exc:
        evals.log(f"{evals.NO} {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
