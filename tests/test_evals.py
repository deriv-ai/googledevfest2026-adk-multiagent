"""The eval scorer: number parsing and the two points per question."""

from pathlib import Path

import pytest
import yaml

from devfest_agents.evals import close_to, numbers_in, score

PRACTICE = Path(__file__).resolve().parent.parent / "evals" / "practice.yaml"

QUESTION = {"id": "q", "question": "Spend and sign-ups?", "agents": ["marketing_agent", "trading_agent"],
            "numbers": [117844.95, 58], "words": ["app-store"]}


def events(answer: str, *specialists: str) -> list[dict]:
    calls = [{"type": "tool_call", "agent": "orchestrator", "tool": name, "kind": "agent"} for name in specialists]
    leaf = {"type": "tool_call", "agent": "marketing_agent", "tool": "channel_summary", "kind": "function"}
    return [{"type": "start"}, *calls, leaf, {"type": "answer", "text": answer, "elapsed_ms": 900}]


def test_numbers_in_reads_money_separators_and_suffixes():
    assert numbers_in("Spend was $117,844.95 (about 117.8k), 58 sign-ups, 1.2M impressions, 4.26%") == \
        [117844.95, 117800.0, 58.0, 1200000.0, 4.26]
    assert numbers_in("over 5 months") == [5.0]


def test_close_to_allows_one_percent_but_small_counts_must_be_exact():
    assert close_to(117844.95, [117800.0]) and not close_to(117844.95, [116000.0])
    assert close_to(18, [18.0]) and not close_to(18, [19.0])


def test_full_marks():
    result = score(QUESTION, events("Marketing: $117.8k on app-store ads, 58 new clients.",
                                    "marketing_agent", "trading_agent"))
    assert (result["route_point"], result["answer_point"], result["missing"]) == (1, 1, [])
    assert result["called_agents"] == ["marketing_agent", "trading_agent"] and result["elapsed_ms"] == 900


def test_route_point_needs_exactly_the_expected_agents():
    extra = score(QUESTION, events("117,844.95 app-store 58", "marketing_agent", "trading_agent", "finance_agent"))
    assert extra["route_point"] == 0 and extra["answer_point"] == 1
    assert score(QUESTION, events("117,844.95 app-store 58", "marketing_agent"))["route_point"] == 0


def test_answer_point_lists_what_is_missing():
    result = score(QUESTION, events("Spend was $117,844.95.", "marketing_agent", "trading_agent"))
    assert result["answer_point"] == 0 and result["missing"] == [58, "app-store"]


def test_error_scores_zero_answer():
    result = score(QUESTION, [{"type": "start"}, {"type": "error", "message": "boom"}])
    assert (result["route_point"], result["answer_point"], result["error"]) == (0, 0, "boom")


@pytest.mark.parametrize("question", yaml.safe_load(PRACTICE.read_text()), ids=lambda q: q["id"])
def test_practice_questions_are_well_formed(question):
    assert set(question) <= {"id", "question", "agents", "numbers", "words"}
    assert question["agents"] and set(question["agents"]) <= {"finance_agent", "trading_agent", "marketing_agent"}
    assert question.get("numbers") or question.get("words")
