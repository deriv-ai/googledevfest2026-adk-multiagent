"""The eval runner: question sets, encryption, 5 marks per question, time limits and setup errors."""

import asyncio
from pathlib import Path

import pytest
import yaml
from pydantic import SecretStr

from devfest_agents import evals
from devfest_agents.evals import (EvalSetupError, encrypt_set, fernet, load_questions, public_questions,
                                  question_set_hash, run_practice, score, summarize, validate_questions)
from devfest_agents.judge import JudgeError
from devfest_agents.runtime import NO_ANSWER_TEXT

from .helpers import events

EVALS = Path(__file__).resolve().parents[2] / "evals"

FULL = [{"id": "q1", "kind": "trap", "question": "TikTok spend?", "agents": ["marketing_agent"],
         "criteria": ["a", "b", "c", "d"]}]


# ---------------------------------------------------------------------------
# Question sets
# ---------------------------------------------------------------------------
def test_practice_set_is_five_valid_questions():
    practice = validate_questions(yaml.safe_load((EVALS / "practice.yaml").read_text()), with_answers=True)
    assert len(practice) == 5
    assert {q["kind"] for q in practice} == {"analysis", "multi-domain", "routing", "trap", "adversarial"}


@pytest.mark.parametrize("change, message", [
    ({"criteria": ["a", "b", "c"]}, "'q1'.*4 criteria"),
    ({"agents": ["sales_agent"]}, "'q1'.*sales_agent"),
    ({"kind": "quiz"}, "'q1'.*quiz"),
    ({"numbers": [1]}, "'q1'.*numbers"),
])
def test_validation_names_the_broken_question(change, message):
    with pytest.raises(EvalSetupError, match=message):
        validate_questions([{**FULL[0], **change}], with_answers=True)


def test_validation_catches_duplicate_ids_and_missing_answers():
    with pytest.raises(EvalSetupError, match="'q1'"):
        validate_questions(FULL + FULL, with_answers=True)
    with pytest.raises(EvalSetupError, match="'q1'"):
        validate_questions(public_questions(FULL), with_answers=True)
    assert validate_questions(public_questions(FULL), with_answers=False)


def test_encrypt_keeps_only_the_questions(tmp_path):
    path = tmp_path / "final.yaml"
    path.write_text(yaml.safe_dump(FULL))
    out = encrypt_set(path, "open sesame")
    assert out == tmp_path / "final.enc"
    assert b"criteria" not in fernet("open sesame").decrypt(out.read_bytes())
    assert load_questions(out, "open sesame") == public_questions(FULL)


def test_an_encrypted_set_needs_the_right_passphrase(tmp_path):
    path = tmp_path / "set.enc"
    path.write_bytes(fernet("open sesame").encrypt(b"- id: a\n"))
    with pytest.raises(EvalSetupError, match="doesn't open"):
        load_questions(path, "wrong")
    with pytest.raises(EvalSetupError, match="KEY="):
        load_questions(path, None)


def test_set_hash_ignores_answers_but_not_wording():
    assert question_set_hash(FULL) == question_set_hash(public_questions(FULL))
    assert question_set_hash(FULL) != question_set_hash([{**FULL[0], "question": "TikTok spend in Q3?"}])


# ---------------------------------------------------------------------------
# Scoring: 1 route mark + 4 answer marks
# ---------------------------------------------------------------------------
Q = {"id": "q", "kind": "multi-domain", "question": "Spend per client?",
     "agents": ["marketing_agent", "trading_agent"], "criteria": ["c1", "c2", "c3", "c4"]}


def verdicts(*passed):
    async def judge(question, answer):
        return [{"passed": p, "reason": f"r{i}"} for i, p in enumerate(passed, 1)]
    return judge


async def must_not_run(question, answer):
    raise AssertionError("the judge ran")


async def test_full_marks():
    result = summarize("q", events("$1,042.88 per client", "marketing_agent", "trading_agent"))
    assert result == {"id": "q", "answer": "$1,042.88 per client", "called_agents": ["marketing_agent", "trading_agent"],
                      "error": None, "elapsed_ms": 900}
    s = await score(Q, result, verdicts(True, True, True, True))
    assert (s["route_mark"], s["answer_marks"], s["judge_error"]) == (1, 4, None)


async def test_route_mark_needs_exactly_the_expected_agents():
    extra = summarize("q", events("x", "marketing_agent", "trading_agent", "finance_agent"))
    assert (await score(Q, extra, verdicts(True, True, True, True)))["route_mark"] == 0
    none_q = {**Q, "agents": []}
    assert (await score(none_q, summarize("q", events("I can't share that.")), verdicts(*[True] * 4)))["route_mark"] == 1


async def test_partial_answer_marks_keep_each_reason():
    s = await score(Q, summarize("q", events("x", "marketing_agent", "trading_agent")), verdicts(True, False, True, False))
    assert s["answer_marks"] == 2
    assert s["criteria"][1] == {"criterion": "c2", "passed": False, "reason": "r2"}


async def test_errored_or_missing_questions_score_zero_without_the_judge():
    errored = summarize("q", [{"type": "start"}, {"type": "error", "message": "Budget has been exceeded!"}])
    for result in (errored, None):
        s = await score({**Q, "agents": []}, result, must_not_run)
        assert (s["route_mark"], s["answer_marks"]) == (0, 0)


def test_the_no_answer_placeholder_counts_as_blank():
    assert summarize("q", events(NO_ANSWER_TEXT, "marketing_agent"))["answer"] == ""


async def test_blank_answer_keeps_the_route_mark_and_skips_the_judge():
    s = await score(Q, summarize("q", events("  ", "marketing_agent", "trading_agent")), must_not_run)
    assert (s["route_mark"], s["answer_marks"]) == (1, 0)


async def test_a_judge_error_costs_the_answer_marks_not_the_run():
    async def broken(question, answer):
        raise JudgeError("the judge failed (TimeoutError)")
    s = await score(Q, summarize("q", events("x", "marketing_agent", "trading_agent")), broken)
    assert (s["route_mark"], s["answer_marks"], s["judge_error"]) == (1, 0, "the judge failed (TimeoutError)")


async def test_practice_report_counts_five_marks_per_question():
    async def asker(question):
        return events("x", "marketing_agent", "trading_agent")
    report = await run_practice([Q], asker, judge=verdicts(True, True, False, True))
    assert (report["score"], report["max_score"]) == (4, 5)
    assert report["results"][0]["marks"] == 4 and report["results"][0]["question"] == "Spend per client?"


async def test_a_slow_question_scores_zero_instead_of_holding_up_the_run():
    async def asker(question):
        if question["id"] == "slow":
            await asyncio.sleep(5)
        return events("x", "marketing_agent", "trading_agent")
    started = asyncio.get_running_loop().time()
    report = await run_practice([Q, Q | {"id": "slow"}], asker, judge=verdicts(*[True] * 4), timeout_s=0.2)
    assert asyncio.get_running_loop().time() - started < 2
    slow = next(r for r in report["results"] if r["id"] == "slow")
    assert slow["marks"] == 0 and "no answer within" in slow["error"] and report["score"] == 5


# ---------------------------------------------------------------------------
# Setup errors
# ---------------------------------------------------------------------------
def test_setup_errors_say_what_to_fix(fake_services, monkeypatch):
    fake_services.settings.gemini_api_key = None
    with pytest.raises(EvalSetupError, match="No LLM key"):
        evals.build_runtime()

    fake_services.settings.gemini_api_key = SecretStr("test-key-not-real")
    monkeypatch.setattr("devfest_agents.agents.build_root_agent", lambda: (_ for _ in ()).throw(NotImplementedError()))
    with pytest.raises(EvalSetupError, match="build\\(\\) isn't finished"):
        evals.build_runtime()
