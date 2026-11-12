"""Score the agents on a question set.

    python -m devfest_agents.evals evals/practice.yaml [--only ID] [--parallel N] > report.json
    python -m devfest_agents.evals evals/final.enc --key PASSPHRASE > report.json
    python -m devfest_agents.evals evals/final.yaml --encrypt --key PASSPHRASE    # writes evals/final.enc

Each question is worth 2 points: one for routing (the orchestrator called exactly
the expected agents), one for the answer (every check on the question passes).
The results table goes to stderr and the JSON report to stdout. For an encrypted
set the questions stay hidden: the table shows only ids, kinds and points.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
import re
import sys
from collections import defaultdict
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import yaml
from cryptography.fernet import Fernet, InvalidToken

from .runtime import AgentRuntime
from .services import get_services

NUMBER_RE = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(k|m|bn)?\b", re.IGNORECASE)
SCALE = {"k": 1e3, "m": 1e6, "bn": 1e9}
TOLERANCE = 0.01
OK, NO = "\033[32m✓\033[0m", "\033[31m✗\033[0m"

JUDGE_PROMPT = """You grade one answer from a company's analytics assistant.

Question: {question}

Answer: {answer}

Pass rule: {rule}

Does the answer follow the pass rule? Reply with PASS or FAIL on the first line,
then one short reason on the second line."""

Judge = Callable[[str, str, str], Awaitable[tuple[bool, str]]]


class EvalSetupError(Exception):
    """Something to fix before any question can run; the message says what."""


# ---------------------------------------------------------------------------
# Checking one answer
# ---------------------------------------------------------------------------
def numbers_in(text: str) -> list[float]:
    """Every number in the text: "$117,844.95" -> 117844.95, "1.2M" -> 1200000.0."""
    return [float(digits.replace(",", "")) * SCALE.get(suffix.lower(), 1)
            for digits, suffix in NUMBER_RE.findall(text)]


def close_to(expected: float, found: list[float]) -> bool:
    return any(abs(value - expected) <= max(abs(expected) * TOLERANCE, 0.005) for value in found)


def missed_checks(question: dict[str, Any], answer: str) -> list[str]:
    """The deterministic checks the answer fails, in words."""
    found, text = numbers_in(answer), answer.lower()
    misses = [f"number {n}" for n in question.get("numbers", []) if not close_to(n, found)]
    misses += [f"word '{w}'" for w in question.get("words", []) if w.lower() not in text]
    misses += [f"should not say '{p}'" for p in question.get("absent", []) if p.lower() in text]
    return misses


async def llm_judge(question: str, answer: str, rule: str) -> tuple[bool, str]:
    import litellm

    settings = get_services().settings
    response = await litellm.acompletion(
        model=settings.effective_router_model,
        messages=[{"role": "user", "content": JUDGE_PROMPT.format(question=question, answer=answer, rule=rule)}],
        temperature=0,
        api_key=settings.llm_api_key,
        api_base=settings.llm_api_base,
        timeout=settings.llm_timeout_seconds,
    )
    lines = (response.choices[0].message.content or "").strip().splitlines() or [""]
    return lines[0].strip().upper().startswith("PASS"), " ".join(lines[1:]).strip() or lines[0]


async def grade(question: dict[str, Any], events: list[dict[str, Any]], judge: Judge = llm_judge) -> dict[str, Any]:
    last = events[-1]
    answer = last.get("text", "") if last["type"] == "answer" else ""
    called = sorted({e["tool"] for e in events if e["type"] == "tool_call" and e["agent"] == "orchestrator"})
    misses = missed_checks(question, answer)
    if answer and not misses and question.get("judge"):
        try:
            passed, reason = await judge(question["question"], answer, question["judge"])
        except Exception as exc:  # noqa: BLE001 - a judge failure costs the point, not the run
            passed, reason = False, f"the judge failed ({type(exc).__name__})"
        if not passed:
            misses.append(f"judge: {reason}")
    return {
        "id": question["id"],
        "kind": question.get("kind", ""),
        "question": question["question"].strip(),
        "expected_agents": sorted(question["agents"]),
        "called_agents": called,
        "route_point": int(called == sorted(question["agents"])),
        "answer_point": int(bool(answer) and not misses),
        "missing": misses,
        "answer": answer,
        "error": last.get("message") if last["type"] == "error" else None,
        "elapsed_ms": last.get("elapsed_ms"),
    }


# ---------------------------------------------------------------------------
# Running a set
# ---------------------------------------------------------------------------
async def ask(runtime: AgentRuntime, question: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        return [e async for e in runtime.ask_stream(f"eval-{question['id']}", question["question"])]
    except Exception as exc:  # noqa: BLE001 - one broken question must not stop the rest
        return [{"type": "error", "message": f"{type(exc).__name__}: {exc}"}]


async def run(questions: list[dict[str, Any]], runtime: AgentRuntime, *, parallel: int = 4,
              judge: Judge = llm_judge, hidden: bool = False) -> dict[str, Any]:
    gate = asyncio.Semaphore(parallel)

    async def one(question):
        async with gate:
            result = await grade(question, await ask(runtime, question), judge)
        log(f"  {OK if result['route_point'] else NO}{OK if result['answer_point'] else NO}  {result['id']}")
        return result

    log(f"Running {len(questions)} question(s), {parallel} at a time...")
    results = await asyncio.gather(*(one(q) for q in questions))
    print_table(results, hidden)
    report = {"score": sum(r["route_point"] + r["answer_point"] for r in results), "max_score": 2 * len(results)}
    if hidden:
        results = [{k: r[k] for k in ("id", "kind", "route_point", "answer_point", "called_agents", "error")}
                   for r in results]
    return report | {"results": results}


def print_table(results: list[dict[str, Any]], hidden: bool) -> None:
    log(f"\n{'question':32} {'kind':13} route  answer  note")
    for r in results:
        note = r["error"] or ("" if hidden else "; ".join(r["missing"]))
        if not r["route_point"]:
            note = f"called {r['called_agents'] or 'no agents'}" + (f"; {note}" if note else "")
        log(f"{r['id'][:32]:32} {r['kind'][:13]:13}   {OK if r['route_point'] else NO}      "
            f"{OK if r['answer_point'] else NO}    {note[:90]}")
    by_kind: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for r in results:
        by_kind[r["kind"]][0] += r["route_point"] + r["answer_point"]
        by_kind[r["kind"]][1] += 2
    total = sum(points for points, _ in by_kind.values())
    log("\n" + "   ".join(f"{kind or 'other'} {p}/{m}" for kind, (p, m) in by_kind.items()))
    log(f"Score: {total} / {2 * len(results)}")


def log(text: str) -> None:
    print(text, file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------
# Setup: catch what isn't wired yet before running anything
# ---------------------------------------------------------------------------
def build_runtime() -> AgentRuntime:
    if not get_services().settings.llm_key_configured:
        raise EvalSetupError("No LLM key configured. Add GEMINI_API_KEY (or LITELLM_GEMINI_API_KEY) to .env, "
                             "then run `make up` again.")
    try:
        from .agents import build_root_agent
        from .agents.common import walk_agents

        root = build_root_agent()
    except NotImplementedError as exc:
        raise EvalSetupError("marketing_agent is in SPECIALISTS, but its build() isn't finished yet "
                             f"({exc}). Finish exercise 2, or take it out of SPECIALISTS for now.") from exc
    except Exception as exc:
        raise EvalSetupError(f"The agents don't build: {type(exc).__name__}: {exc}\n"
                             "Fix that first. `make logs` may show the full error.") from exc
    if "marketing_agent" not in {agent.name for agent in walk_agents(root)}:
        log("Note: marketing_agent isn't plugged into the orchestrator yet (exercise 3), "
            "so marketing questions will fail. That's expected for now.\n")
    return AgentRuntime(root)


def fernet(passphrase: str) -> Fernet:
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(passphrase.encode()).digest()))


def load_questions(path: Path, key: str | None) -> list[dict[str, Any]]:
    if not path.exists():
        raise EvalSetupError(f"{path} doesn't exist.")
    data = path.read_bytes()
    if path.suffix == ".enc":
        if not key:
            raise EvalSetupError("This question set is encrypted. Pass the passphrase: make eval-final KEY=...")
        try:
            data = fernet(key).decrypt(data)
        except InvalidToken:
            raise EvalSetupError("That passphrase doesn't open this question set. Check it and try again.") from None
    return yaml.safe_load(data)


async def main_async(questions: list[dict[str, Any]], parallel: int, hidden: bool) -> dict[str, Any]:
    try:
        return await run(questions, build_runtime(), parallel=parallel, hidden=hidden)
    finally:
        await get_services().database().close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Score the agents on a question set.")
    parser.add_argument("questions", type=Path, help="evals/practice.yaml, or an encrypted .enc set")
    parser.add_argument("--key", help="passphrase of an encrypted set")
    parser.add_argument("--only", help="run only the question with this id")
    parser.add_argument("--parallel", type=int, default=4, help="questions to run at the same time (default 4)")
    parser.add_argument("--encrypt", action="store_true", help="write an encrypted copy of the set (needs --key)")
    args = parser.parse_args()

    try:
        if args.encrypt:
            if not args.key:
                raise EvalSetupError("--encrypt needs --key.")
            out = args.questions.with_suffix(".enc")
            out.write_bytes(fernet(args.key).encrypt(args.questions.read_bytes()))
            log(f"Wrote {out}")
            return
        questions = load_questions(args.questions, args.key)
        if args.only:
            questions = [q for q in questions if q["id"] == args.only]
            if not questions:
                raise EvalSetupError(f"No question with id {args.only!r}.")
        report = asyncio.run(main_async(questions, max(1, args.parallel), hidden=args.questions.suffix == ".enc"))
    except EvalSetupError as exc:
        log(f"{NO} {exc}")
        sys.exit(1)
    json.dump(report, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
