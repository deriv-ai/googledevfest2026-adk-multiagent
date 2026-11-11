"""Score the agents on a question set.

    python -m devfest_agents.evals evals/practice.yaml [--only ID] > report.json

Each question runs as a fresh conversation and is worth 2 points: one when the
orchestrator called exactly the expected agents, one when the answer contains
every expected number (within 1%) and word. Progress goes to stderr, the JSON
report to stdout.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

from .runtime import AgentRuntime
from .services import get_services

NUMBER_RE = re.compile(r"(\d[\d,]*(?:\.\d+)?)\s*(k|m|bn)?\b", re.IGNORECASE)
SCALE = {"k": 1e3, "m": 1e6, "bn": 1e9}
TOLERANCE = 0.01


def numbers_in(text: str) -> list[float]:
    """Every number in the text: "$117,844.95" -> 117844.95, "1.2M" -> 1200000.0."""
    return [float(digits.replace(",", "")) * SCALE.get(suffix.lower(), 1)
            for digits, suffix in NUMBER_RE.findall(text)]


def close_to(expected: float, found: list[float]) -> bool:
    return any(abs(value - expected) <= max(abs(expected) * TOLERANCE, 0.5) for value in found)


def score(question: dict[str, Any], events: list[dict[str, Any]]) -> dict[str, Any]:
    last = events[-1]
    answer = last.get("text", "") if last["type"] == "answer" else ""
    called = sorted({e["tool"] for e in events if e["type"] == "tool_call" and e["agent"] == "orchestrator"})
    found = numbers_in(answer)
    missing = [n for n in question.get("numbers", []) if not close_to(n, found)]
    missing += [w for w in question.get("words", []) if w.lower() not in answer.lower()]
    return {
        "id": question["id"],
        "question": question["question"],
        "expected_agents": sorted(question["agents"]),
        "called_agents": called,
        "route_point": int(called == sorted(question["agents"])),
        "answer_point": int(bool(answer) and not missing),
        "missing": missing,
        "answer": answer,
        "error": last.get("message") if last["type"] == "error" else None,
        "elapsed_ms": last.get("elapsed_ms"),
    }


async def run(questions: list[dict[str, Any]], runtime: AgentRuntime) -> dict[str, Any]:
    results = []
    for i, question in enumerate(questions, 1):
        log(f"[{i}/{len(questions)}] {question['id']}")
        events = [e async for e in runtime.ask_stream(f"eval-{question['id']}", question["question"])]
        result = score(question, events)
        results.append(result)
        log(f"    route {result['route_point']}  answer {result['answer_point']}  "
            f"called {result['called_agents']}" + (f"  missing {result['missing']}" if result["missing"] else ""))
    total = sum(r["route_point"] + r["answer_point"] for r in results)
    log(f"\nScore: {total} / {2 * len(results)}")
    return {"score": total, "max_score": 2 * len(results), "results": results}


def log(text: str) -> None:
    print(text, file=sys.stderr, flush=True)


async def main_async(questions: list[dict[str, Any]]) -> dict[str, Any]:
    try:
        return await run(questions, AgentRuntime())
    finally:
        await get_services().database().close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Score the agents on a question set.")
    parser.add_argument("questions", type=Path, help="YAML file of questions, e.g. evals/practice.yaml")
    parser.add_argument("--only", help="run only the question with this id")
    args = parser.parse_args()

    questions = yaml.safe_load(args.questions.read_text())
    if args.only:
        questions = [q for q in questions if q["id"] == args.only]
        if not questions:
            parser.error(f"no question with id {args.only!r}")
    if not get_services().settings.llm_key_configured:
        parser.error("no LLM key configured: add GEMINI_API_KEY (or LITELLM_GEMINI_API_KEY) to .env")

    json.dump(asyncio.run(main_async(questions)), sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
