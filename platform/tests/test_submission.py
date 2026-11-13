"""`make eval-final`: the answers file, resuming a run, and a key that runs out of budget."""

import json

import pytest
import yaml

from devfest_agents import evals
from devfest_agents.evals import fernet, question_set_hash
from devfest_agents.submission import NOT_RUN, collect, is_budget_error, load_previous

from .helpers import events

QUESTIONS = [{"id": f"q{i}", "kind": "lookup", "question": f"Question {i}?"} for i in (1, 2, 3)]


class Asker:
    """Answers every question, or fails every one with `error`; records what it was asked."""

    def __init__(self, error: str | None = None):
        self.error, self.asked = error, []

    async def __call__(self, question):
        self.asked.append(question["id"])
        if self.error:
            return [{"type": "start"}, {"type": "error", "message": self.error}]
        return events("answer", "marketing_agent")


def test_budget_errors_are_recognised():
    assert is_budget_error("The assistant failed to answer (BadRequestError: litellm.BadRequestError: "
                           "Budget has been exceeded! Key=sk-... Current cost: 5.01, Max budget: 5.0).")
    assert is_budget_error("ExceededTokenBudget: Current spend for token: 5.1")
    assert not is_budget_error("The assistant failed to answer (Timeout).") and not is_budget_error(None)


async def test_submission_has_the_agreed_shape(fake_services):
    sub = await collect(QUESTIONS, Asker(), name="Ada Tan", commit="abc1234", previous=None)
    assert set(sub) == {"format", "name", "generated_at", "commit", "agent_model", "router_model", "question_set", "results"}
    assert sub["format"] == 1 and sub["name"] == "Ada Tan" and sub["question_set"] == question_set_hash(QUESTIONS)
    assert [r["id"] for r in sub["results"]] == ["q1", "q2", "q3"]
    assert set(sub["results"][0]) == {"id", "answer", "called_agents", "error", "elapsed_ms"}


async def test_resume_reruns_only_errored_and_missing_questions(fake_services):
    kept = {"id": "q1", "answer": "kept", "called_agents": ["marketing_agent"], "error": None, "elapsed_ms": 5}
    previous = {"question_set": question_set_hash(QUESTIONS),
                "results": [kept, {"id": "q2", "answer": "", "called_agents": [], "error": "boom", "elapsed_ms": None}]}
    asker = Asker()
    sub = await collect(QUESTIONS, asker, name="Ada", commit="", previous=previous)
    assert sorted(asker.asked) == ["q2", "q3"] and sub["results"][0] == kept


def test_previous_file_is_ignored_when_missing_broken_or_from_another_set(tmp_path):
    path = tmp_path / "submission.json"
    assert load_previous(path, "h") is None
    path.write_text("{oops")
    assert load_previous(path, "h") is None
    path.write_text(json.dumps({"question_set": "other", "results": []}))
    assert load_previous(path, "h") is None
    path.write_text(json.dumps({"question_set": "h", "results": []}))
    assert load_previous(path, "h") == {"question_set": "h", "results": []}


async def test_running_out_of_budget_stops_but_still_returns_a_file(fake_services):
    asker = Asker(error="Budget has been exceeded! Key=x Current cost: 5.01, Max budget: 5.0")
    sub = await collect(QUESTIONS, asker, name="Ada", commit="", previous=None, parallel=1)
    assert asker.asked == ["q1"]
    assert [r["error"] for r in sub["results"][1:]] == [NOT_RUN, NOT_RUN]


def test_the_hidden_set_needs_a_name(tmp_path, monkeypatch, capsys):
    path = tmp_path / "final.enc"
    path.write_bytes(fernet("k").encrypt(yaml.safe_dump(QUESTIONS).encode()))
    monkeypatch.setattr("sys.argv", ["evals", str(path), "--key", "k"])
    with pytest.raises(SystemExit):
        evals.main()
    assert "NAME=" in capsys.readouterr().err


async def test_the_resume_message_counts_in_plain_english(fake_services, capsys):
    previous = {"question_set": question_set_hash(QUESTIONS),
                "results": [{"id": q, "answer": "kept", "called_agents": [], "error": None, "elapsed_ms": 5}
                            for q in ("q1", "q2")]}
    await collect(QUESTIONS, Asker(), name="Ada", commit="", previous=previous)
    assert "keeping 2 answers, running the 1 question that failed or didn't run" in capsys.readouterr().err


def test_stray_prints_never_reach_the_answers_file(tmp_path, monkeypatch, capsys, fake_services):
    """LiteLLM prints a help banner on API errors, and a participant's tool may print too: the
    answers file goes to stdout, so anything else printed there would corrupt it."""
    path = tmp_path / "final.enc"
    path.write_bytes(fernet("k").encrypt(yaml.safe_dump(QUESTIONS).encode()))

    async def noisy_ask(runtime, question):
        print("Give Feedback / Get Help: https://github.com/BerriAI/litellm/issues/new")
        return events("answer", "marketing_agent")

    monkeypatch.setattr(evals, "build_runtime", lambda: object())
    monkeypatch.setattr(evals, "ask", noisy_ask)
    monkeypatch.setattr("sys.argv", ["evals", str(path), "--key", "k", "--name", "Ada"])
    evals.main()
    captured = capsys.readouterr()
    assert json.loads(captured.out)["name"] == "Ada"
    assert "Give Feedback" in captured.err
