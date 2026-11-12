"""The competition judge: reading submissions, summing points, the leaderboard."""

import os
import zipfile

import pytest

from devfest_agents.judge import (JudgeError, Submission, points_by_kind, read_submissions, shared_error, sse_events,
                                  unpack_my_agent, version)
from devfest_agents.leaderboard import ranked, render


def make_zip(path, files):
    with zipfile.ZipFile(path, "w") as zf:
        for name, text in files.items():
            zf.writestr(name, text)


def test_each_zip_or_folder_is_a_submission_and_the_newest_upload_counts(tmp_path):
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    make_zip(inbox / "Ada.zip", {"my_agent/team.py": "old"})
    (inbox / "Team Bo").mkdir()
    (inbox / "Team Bo" / "team.py").write_text("x")
    (inbox / "Ada (1).zip").write_bytes((inbox / "Ada.zip").read_bytes())
    (inbox / "notes.txt").write_text("not a submission")
    os.utime(inbox / "Ada.zip", (1000, 1000))
    os.utime(inbox / "Ada (1).zip", (2000, 2000))
    subs = read_submissions(inbox, tmp_path / "out")
    assert sorted((s.name, s.path.name) for s in subs) == [("Ada", "Ada (1).zip"), ("Team Bo", "Team Bo")]


def test_a_drive_download_zip_is_unpacked_and_its_wrapper_folder_skipped(tmp_path):
    inner = tmp_path / "Ada.zip"
    make_zip(inner, {"my_agent/team.py": "x"})
    download = tmp_path / "drive-download.zip"
    make_zip(download, {"Submissions/Ada.zip": inner.read_bytes()})
    subs = read_submissions(download, tmp_path / "out")
    assert [s.name for s in subs] == ["Ada"]


def test_my_agent_is_found_however_it_was_zipped_and_junk_is_dropped(tmp_path):
    for i, files in enumerate([{"my_agent/team.py": "x", "my_agent/__pycache__/a.pyc": "junk"},
                               {"team.py": "x", ".DS_Store": "junk"},
                               {"Ada/my_agent/team.py": "x", "__MACOSX/Ada/._team.py": "junk"}]):
        make_zip(tmp_path / f"s{i}.zip", files)
        my_agent, ver = unpack_my_agent(Submission("Ada", tmp_path / f"s{i}.zip"), tmp_path / f"work{i}")
        assert sorted(p.name for p in my_agent.rglob("*")) == ["team.py"]
        assert ver == version(my_agent)


def test_a_zip_without_team_py_or_with_escaping_paths_is_refused(tmp_path):
    make_zip(tmp_path / "empty.zip", {"README.md": "hi"})
    with pytest.raises(JudgeError, match="no team.py"):
        unpack_my_agent(Submission("x", tmp_path / "empty.zip"), tmp_path / "w1")
    make_zip(tmp_path / "evil.zip", {"../../evil.py": "x", "team.py": "x"})
    with pytest.raises(JudgeError, match="outside"):
        unpack_my_agent(Submission("x", tmp_path / "evil.zip"), tmp_path / "w2")


def test_the_version_changes_only_when_a_file_does(tmp_path):
    (tmp_path / "team.py").write_text("a")
    first = version(tmp_path)
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "team.pyc").write_text("junk")
    assert version(tmp_path) == first
    (tmp_path / "team.py").write_text("b")
    assert version(tmp_path) != first


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
                    "version": "abcdef1234", "error": "the app didn't start"}])
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
