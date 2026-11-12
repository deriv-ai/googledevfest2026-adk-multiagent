"""The competition judge: reading submissions, summing points, the leaderboard."""

from devfest_agents.judge import Submission, https_url, points_by_kind, read_submissions, shared_error, sse_events
from devfest_agents.leaderboard import ranked, render


def test_a_form_export_reads_as_it_is_and_the_latest_row_counts(tmp_path):
    csv = tmp_path / "subs.csv"
    csv.write_text("Timestamp,Your name,Fork URL,Commit (optional)\n"
                   "2026-11-20 10:01,Ada,https://github.com/ada/fork,abc123\n"
                   "2026-11-20 10:02,Bo,git@github.com:bo/fork.git,\n"
                   "2026-11-20 10:05,Ada,https://github.com/ada/fork,def456\n"
                   "2026-11-20 10:06,,https://github.com/nobody/fork,\n")
    subs = read_submissions(csv)
    assert subs == [Submission("Ada", "https://github.com/ada/fork", "def456", "2026-11-20 10:05"),
                    Submission("Bo", "https://github.com/bo/fork.git", "", "2026-11-20 10:02")]


def test_ssh_urls_become_https():
    assert https_url("git@github.com:me/fork.git") == "https://github.com/me/fork.git"
    assert https_url("https://github.com/me/fork") == "https://github.com/me/fork"


def test_sse_lines_become_events():
    lines = ['data: {"type": "start"}', "", ": ping", 'data: {"type": "answer", "text": "hi"}']
    assert sse_events(lines) == [{"type": "start"}, {"type": "answer", "text": "hi"}]


def test_points_add_up_per_kind():
    results = [{"kind": "lookup", "route_point": 1, "answer_point": 1, "error": None},
               {"kind": "lookup", "route_point": 1, "answer_point": 0, "error": None},
               {"kind": "trap", "route_point": 0, "answer_point": 0, "error": "boom"}]
    assert points_by_kind(results) == {"lookup": [3, 4], "trap": [0, 2]}
    assert shared_error(results) is None
    assert shared_error([{"error": "agents don't build"}] * 3) == "agents don't build"


def test_ties_go_to_the_earlier_submission():
    rows = [{"name": "late", "score": 30, "submitted_at": "10:30"},
            {"name": "early", "score": 30, "submitted_at": "10:10"},
            {"name": "top", "score": 35, "submitted_at": "10:40"}]
    assert [r["name"] for r in ranked(rows)] == ["top", "early", "late"]


def test_the_page_escapes_names_and_shows_errors():
    page = render([{"name": "<b>x</b>", "score": 3, "max_score": 44, "by_kind": {"trap": [1, 6]},
                    "commit": "abcdef1234", "error": "the app didn't start"}])
    assert "&lt;b&gt;x&lt;/b&gt;" in page and "<b>x</b>" not in page
    assert "the app didn&#x27;t start" in page and "abcdef1" in page and "1/6" in page
    assert "No submissions judged yet." in render([])


def test_the_board_keeps_earlier_runs_and_each_names_latest_result(tmp_path):
    import json
    import os

    from devfest_agents.judge import saved_results

    results = tmp_path / "results"
    results.mkdir()
    for i, (file, name, score) in enumerate([("ada-1.json", "Ada", 10), ("bo-1.json", "Bo", 20), ("ada-2.json", "Ada", 30)]):
        (results / file).write_text(json.dumps({"name": name, "score": score}))
        os.utime(results / file, (1000 + i, 1000 + i))
    assert {name: r["score"] for name, r in saved_results(tmp_path).items()} == {"ada": 30, "bo": 20}
