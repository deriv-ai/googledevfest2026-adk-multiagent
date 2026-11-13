"""Score the agents on a question set, and run the competition set.

    python -m devfest_agents.evals evals/practice.yaml [--only ID] [--parallel N] [--timeout S] > report.json
    python -m devfest_agents.evals evals/final.enc --key PASSPHRASE --name NAME [--previous FILE] > submission.json
    python -m devfest_agents.evals evals/final.yaml --encrypt --key PASSPHRASE    # writes evals/final.enc

Each question is worth 5 marks: 1 for routing (the orchestrator called exactly the
expected agents) and 4 for the answer (an LLM judge checks it against the question's
4 criteria, one mark each). The results table goes to stderr and the JSON report to
stdout. The competition set is encrypted and holds no answers: participants run it
and hand in what their agents said, and the facilitators score that.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import json
import sys
from collections import defaultdict
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import yaml
from cryptography.fernet import Fernet, InvalidToken

from .judge import CRITERIA_PER_QUESTION, Judge, JudgeError, make_judge
from .runtime import NO_ANSWER_TEXT, AgentRuntime
from .services import get_services

OK, NO = "\033[32m✓\033[0m", "\033[31m✗\033[0m"
PARALLEL = 8     # questions at a time; lower it if your LLM key hits rate limits
TIMEOUT_S = 120  # a question with no answer by then scores 0, so one slow question can't hold up the run
KINDS = frozenset({"lookup", "analysis", "multi-domain", "routing", "trap", "adversarial"})
SPECIALIST_NAMES = frozenset({"finance_agent", "trading_agent", "marketing_agent", "news_agent"})
PUBLIC_FIELDS = ("id", "kind", "question")  # all an encrypted competition set holds
ANSWER_FIELDS = ("agents", "criteria")      # the answer key; never leaves the facilitators for the competition

Asker = Callable[[dict[str, Any]], Awaitable[list[dict[str, Any]]]]  # question -> the turn's events


class EvalSetupError(Exception):
    """Something to fix before any question can run; the message says what."""


# ---------------------------------------------------------------------------
# One question: what the agents did, and its marks
# ---------------------------------------------------------------------------
def summarize(question_id: str, events: list[dict[str, Any]]) -> dict[str, Any]:
    """What one turn produced: the answer, the specialists the orchestrator called, any error."""
    last = events[-1]
    answer = last.get("text", "") if last["type"] == "answer" else ""
    return {
        "id": question_id,
        "answer": "" if answer == NO_ANSWER_TEXT else answer,  # the app's stand-in for "no answer" is not an answer
        "called_agents": sorted({e["tool"] for e in events if e["type"] == "tool_call" and e["agent"] == "orchestrator"}),
        "error": last.get("message") if last["type"] == "error" else None,
        "elapsed_ms": last.get("elapsed_ms"),
    }


async def score(question: dict[str, Any], result: dict[str, Any] | None, judge: Judge) -> dict[str, Any]:
    """1 route mark and up to 4 answer marks. A question that errored or never ran scores 0."""
    marks: dict[str, Any] = {"route_mark": 0, "answer_marks": 0, "criteria": [], "judge_error": None}
    if result is None or result.get("error"):
        return marks
    marks["route_mark"] = int(sorted(result.get("called_agents") or []) == sorted(question["agents"]))
    answer = result.get("answer") or ""
    if not answer.strip():
        return marks
    try:
        verdicts = await judge(question, answer)
    except JudgeError as exc:
        return marks | {"judge_error": str(exc)}
    marks["criteria"] = [{"criterion": c, "passed": v["passed"], "reason": v["reason"]}
                         for c, v in zip(question["criteria"], verdicts)]
    marks["answer_marks"] = sum(v["passed"] for v in verdicts)
    return marks


# ---------------------------------------------------------------------------
# Running a set
# ---------------------------------------------------------------------------
async def ask(runtime: AgentRuntime, question: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        return [e async for e in runtime.ask_stream(f"eval-{question['id']}", question["question"])]
    except Exception as exc:  # noqa: BLE001 - one broken question must not stop the rest
        return [{"type": "error", "message": f"{type(exc).__name__}: {exc}"}]


async def answer_within(asker: Asker, question: dict[str, Any], timeout_s: float) -> list[dict[str, Any]]:
    try:
        return await asyncio.wait_for(asker(question), timeout_s)
    except TimeoutError:
        return [{"type": "error", "message": f"no answer within {timeout_s:.0f} s"}]


def tool_calls(events: list[dict[str, Any]]) -> list[str]:
    return [f"{e['agent']} -> {e['tool']}({json.dumps(e.get('args', {}), ensure_ascii=False)})"
            for e in events if e["type"] == "tool_call"]


async def run_practice(questions: list[dict[str, Any]], asker: Asker, *, judge: Judge,
                       parallel: int = PARALLEL, timeout_s: float = TIMEOUT_S) -> dict[str, Any]:
    gate = asyncio.Semaphore(parallel)

    async def one(question: dict[str, Any]) -> dict[str, Any]:
        async with gate:
            events = await answer_within(asker, question, timeout_s)
            result = summarize(question["id"], events)
            marks = await score(question, result, judge)
        row = {"kind": question["kind"], "question": question["question"].strip(),
               "expected_agents": sorted(question["agents"]), **result, **marks,
               "marks": marks["route_mark"] + marks["answer_marks"], "tools": tool_calls(events)}
        log(f"  {row['marks']}/5  {row['id']}")
        return row

    log(f"Running {len(questions)} question(s), {parallel} at a time...")
    results = await asyncio.gather(*(one(q) for q in questions))
    print_table(results)
    return {"score": sum(r["marks"] for r in results), "max_score": 5 * len(results), "results": results}


def print_table(results: list[dict[str, Any]]) -> None:
    log(f"\n{'question':32} {'kind':13} route  answer  note")
    for r in results:
        failed = next((c["reason"] for c in r["criteria"] if not c["passed"]), "")
        note = r["error"] or r["judge_error"] or failed
        if not r["route_mark"] and not r["error"]:
            note = f"called {r['called_agents'] or 'no agents'}" + (f"; {note}" if note else "")
        log(f"{r['id'][:32]:32} {r['kind'][:13]:13}   {OK if r['route_mark'] else NO}     "
            f"{r['answer_marks']}/4    {note[:90]}")
    by_kind: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for r in results:
        by_kind[r["kind"]][0] += r["marks"]
        by_kind[r["kind"]][1] += 5
    log("\n" + "   ".join(f"{kind or 'other'} {p}/{m}" for kind, (p, m) in by_kind.items()))
    log(f"Score: {sum(r['marks'] for r in results)} / {5 * len(results)}")


def log(text: str) -> None:
    print(text, file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------
# Setup: catch what isn't wired yet before running anything
# ---------------------------------------------------------------------------
def build_runtime() -> AgentRuntime:
    if not get_services().settings.llm_key_configured:
        raise EvalSetupError("No LLM key configured. Add LLM_API_KEY (and AGENT_MODEL) to .env, "
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


# ---------------------------------------------------------------------------
# Question sets
# ---------------------------------------------------------------------------
def validate_questions(questions: Any, *, with_answers: bool) -> list[dict[str, Any]]:
    """Every question is well formed. with_answers: it also carries its agents and 4 criteria."""
    if not isinstance(questions, list) or not all(isinstance(q, dict) for q in questions):
        raise EvalSetupError("A question set is a list of questions.")
    fields = set(PUBLIC_FIELDS) | (set(ANSWER_FIELDS) if with_answers else set())
    seen: set[str] = set()
    for q in questions:
        qid = q.get("id")
        if qid in seen:
            raise EvalSetupError(f"Question {qid!r} appears twice.")
        seen.add(qid)
        if unknown := sorted(set(q) - fields):
            raise EvalSetupError(f"Question {qid!r} has unknown fields: {', '.join(unknown)}.")
        if missing := sorted(fields - set(q)):
            raise EvalSetupError(f"Question {qid!r} is missing: {', '.join(missing)}.")
        if q["kind"] not in KINDS:
            raise EvalSetupError(f"Question {qid!r} has an unknown kind: {q['kind']}.")
        if not with_answers:
            continue
        if not isinstance(q["agents"], list) or set(q["agents"]) - SPECIALIST_NAMES:
            raise EvalSetupError(f"Question {qid!r} names an unknown agent: {q['agents']}.")
        criteria = q["criteria"]
        if (not isinstance(criteria, list) or len(criteria) != CRITERIA_PER_QUESTION
                or not all(isinstance(c, str) and c.strip() for c in criteria)):
            raise EvalSetupError(f"Question {qid!r} needs exactly {CRITERIA_PER_QUESTION} criteria.")
    return questions


def public_questions(questions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{field: q[field] for field in PUBLIC_FIELDS} for q in questions]


def question_set_hash(questions: list[dict[str, Any]]) -> str:
    """Names one question set, answers or not, so an answers file can't be scored against another set."""
    canonical = json.dumps(public_questions(questions), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def fernet(passphrase: str) -> Fernet:
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(passphrase.encode()).digest()))


def load_questions(path: Path, key: str | None = None) -> list[dict[str, Any]]:
    if not path.exists():
        raise EvalSetupError(f"{path} doesn't exist.")
    data = path.read_bytes()
    if path.suffix == ".enc":
        if not key:
            raise EvalSetupError("This question set is locked. Add the passphrase: make eval-final KEY=<passphrase> NAME=<your name>")
        try:
            data = fernet(key).decrypt(data)
        except InvalidToken:
            raise EvalSetupError("That passphrase doesn't open this question set. Check it and try again.") from None
    return yaml.safe_load(data.decode("utf-8"))


def encrypt_set(path: Path, key: str) -> Path:
    """Write <set>.enc next to the set: the questions only, without their answer key."""
    questions = validate_questions(load_questions(path), with_answers=True)
    out = path.with_suffix(".enc")
    out.write_bytes(fernet(key).encrypt(
        yaml.safe_dump(public_questions(questions), sort_keys=False, allow_unicode=True).encode("utf-8")))
    return out


async def main_async(questions: list[dict[str, Any]], parallel: int, timeout_s: float) -> dict[str, Any]:
    runtime = build_runtime()
    try:
        return await run_practice(questions, lambda question: ask(runtime, question), judge=make_judge(),
                                  parallel=parallel, timeout_s=timeout_s)
    finally:
        await get_services().database().close()


async def main_final(questions: list[dict[str, Any]], args: argparse.Namespace) -> dict[str, Any]:
    from .submission import collect, load_previous

    runtime = build_runtime()
    try:
        return await collect(questions, lambda question: ask(runtime, question), name=args.name.strip(),
                             commit=args.commit, previous=load_previous(args.previous, question_set_hash(questions)),
                             parallel=max(1, args.parallel), timeout_s=args.timeout)
    finally:
        await get_services().database().close()


def main() -> None:
    # The JSON report is the only thing on stdout: the Makefile writes it straight to a file. LiteLLM
    # prints help banners on API errors, and a participant's tool may print too, so while the agents
    # run, anything printed goes to stderr (the terminal) instead.
    out, sys.stdout = sys.stdout, sys.stderr
    try:
        report = run_cli()
    finally:
        sys.stdout = out
    if report is not None:
        json.dump(report, out, indent=2)
        print(file=out)


def run_cli() -> dict[str, Any] | None:
    parser = argparse.ArgumentParser(description="Score the agents on a question set.")
    parser.add_argument("questions", type=Path, help="a question set, e.g. evals/practice.yaml")
    parser.add_argument("--only", help="run only the question with this id")
    parser.add_argument("--parallel", type=int, default=PARALLEL, help=f"questions at the same time (default {PARALLEL})")
    parser.add_argument("--timeout", type=float, default=TIMEOUT_S, help=f"seconds per question (default {TIMEOUT_S})")
    parser.add_argument("--key", help="the passphrase of an encrypted set")
    parser.add_argument("--encrypt", action="store_true", help="write <set>.enc: the questions only (needs --key)")
    parser.add_argument("--name", default="", help="your name or team, for the competition's answers file")
    parser.add_argument("--commit", default="", help="the git commit your agents ran from")
    parser.add_argument("--previous", type=Path, help="an earlier answers file to resume from")
    args = parser.parse_args()

    try:
        if args.encrypt:
            if not args.key:
                raise EvalSetupError("--encrypt needs --key.")
            log(f"Wrote {encrypt_set(args.questions, args.key)}")
            return None
        if args.questions.suffix == ".enc":
            if not args.name.strip():
                raise EvalSetupError("Add your name: make eval-final KEY=<passphrase> NAME=<your name>")
            questions = validate_questions(load_questions(args.questions, args.key), with_answers=False)
            return asyncio.run(main_final(questions, args))
        questions = validate_questions(load_questions(args.questions, args.key), with_answers=True)
        if args.only:
            questions = [q for q in questions if q["id"] == args.only]
            if not questions:
                raise EvalSetupError(f"No question with id {args.only!r}.")
        return asyncio.run(main_async(questions, max(1, args.parallel), args.timeout))
    except EvalSetupError as exc:
        log(f"{NO} {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
