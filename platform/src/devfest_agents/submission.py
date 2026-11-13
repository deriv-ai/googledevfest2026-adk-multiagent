"""The competition run: ask every hidden question and write down what the agents said.

`make eval-final KEY=... NAME=...` decrypts evals/final.enc (questions only, no answers),
runs each question through the participant's agents and prints one JSON file of answers
to upload. Nothing is scored here: the facilitators score every file centrally.

Running it again keeps the questions already answered and only re-runs the ones that
failed or never ran, so a hiccup never costs a question twice. When the LLM key runs out
of budget, the run stops starting new questions and still writes the file.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

from .evals import PARALLEL, TIMEOUT_S, Asker, answer_within, log, question_set_hash, summarize
from .services import get_services

FORMAT = 1
NOT_RUN = "Not run: your key ran out of budget."


def is_budget_error(message: str | None) -> bool:
    """LiteLLM's proxy says "Budget has been exceeded! Key=..." (or "ExceededTokenBudget")."""
    text = (message or "").lower()
    return "budget" in text and "exceed" in text


def load_previous(path: Path | None, set_hash: str) -> dict[str, Any] | None:
    """An earlier answers file for this question set, or None."""
    if path is None or not path.is_file():
        return None
    try:
        previous = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(previous, dict) or previous.get("question_set") != set_hash:
        return None
    return previous


async def collect(questions: list[dict[str, Any]], asker: Asker, *, name: str, commit: str,
                  previous: dict[str, Any] | None, parallel: int = PARALLEL,
                  timeout_s: float = TIMEOUT_S) -> dict[str, Any]:
    ids = {q["id"] for q in questions}
    kept = {r["id"]: r for r in (previous or {}).get("results", [])
            if isinstance(r, dict) and r.get("id") in ids and not r.get("error")}
    todo = [q for q in questions if q["id"] not in kept]
    if previous is not None:
        log(f"Found your earlier file: keeping {len(kept)} answer{'' if len(kept) == 1 else 's'}, "
            f"running the {len(todo)} question{'' if len(todo) == 1 else 's'} that failed or didn't run.")
    else:
        log(f"Running {len(todo)} questions, {parallel} at a time...")

    gate = asyncio.Semaphore(parallel)
    out_of_budget = asyncio.Event()

    async def one(question: dict[str, Any]) -> dict[str, Any]:
        async with gate:
            if out_of_budget.is_set():
                return {"id": question["id"], "answer": "", "called_agents": [], "error": NOT_RUN, "elapsed_ms": None}
            result = summarize(question["id"], await answer_within(asker, question, timeout_s))
        if is_budget_error(result["error"]):
            out_of_budget.set()
        log(f"  error     {result['id']}: {result['error'][:80]}" if result["error"] else f"  answered  {result['id']}")
        return result

    ran = {r["id"]: r for r in await asyncio.gather(*(one(q) for q in todo))}
    results = [kept.get(q["id"]) or ran[q["id"]] for q in questions]
    answered = sum(1 for r in results if not r["error"])
    if out_of_budget.is_set():
        log(f"\nYour key has run out of budget. Your file has {answered} of {len(results)} answers; "
            "upload it as it is.")
    else:
        log(f"\n{answered} of {len(results)} questions answered.")

    settings = get_services().settings
    return {
        "format": FORMAT,
        "name": name,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "commit": commit,
        "agent_model": settings.effective_agent_model,
        "router_model": settings.effective_router_model,
        "question_set": question_set_hash(questions),
        "results": results,
    }
