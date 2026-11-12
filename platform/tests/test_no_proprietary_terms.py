"""Guardrail: the repo must not mention any proprietary source names.

The banned words are stored reversed so this file does not contain them itself.
Only files git would track are scanned (`git ls-files --cached --others
--exclude-standard`), so ignored files such as `.env` are never read.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

# Reversed spellings; `.` in the second entry allows "x y", "x_y", "x-y", "xy".
_REVERSED = ["vired", "ecnanif.?niarb", "htailog", "redartd", "5tmd", "redartc", "tcaatni", "tfys"]
BANNED = re.compile("|".join(w[::-1] for w in _REVERSED), re.IGNORECASE)

EXCLUDED_PARTS = {".git", ".venv", "node_modules", "__pycache__"}
EXCLUDED_PATHS = {"platform/uv.lock", "platform/web/package-lock.json"}
EXCLUDED_PREFIXES = ("platform/web/dist/",)
BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp", ".woff", ".woff2", ".ttf", ".pdf", ".zip"}


def _candidate_files() -> list[Path]:
    try:
        out = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=REPO, check=True, capture_output=True,
        ).stdout.decode()
        rels = [r for r in out.split("\0") if r]
    except (OSError, subprocess.CalledProcessError):  # no git: walk, skipping secrets
        rels = [p.relative_to(REPO).as_posix() for p in REPO.rglob("*")
                if p.is_file() and not p.name.startswith(".env")
                or p.name == ".env.example"]
    files = []
    for rel in rels:
        parts = set(Path(rel).parts)
        if parts & EXCLUDED_PARTS or rel in EXCLUDED_PATHS or rel.startswith(EXCLUDED_PREFIXES):
            continue
        if Path(rel).name == ".env" or Path(rel).suffix.lower() in BINARY_SUFFIXES:
            continue
        path = REPO / rel
        if path.is_file():
            files.append(path)
    return files


def test_pattern_self_check():
    # sanity: the decoded pattern really matches what it should (built from fragments)
    assert BANNED.search("Brain" + "-" + "Finance")
    assert BANNED.search("x" + "SYF" + "T")
    assert not BANNED.search("Nimbus Markets finance brain")


def test_scans_some_files():
    names = {p.relative_to(REPO).as_posix() for p in _candidate_files()}
    assert "compose.yaml" in names
    assert ".env" not in names


@pytest.mark.parametrize("path", _candidate_files(), ids=lambda p: p.relative_to(REPO).as_posix())
def test_file_has_no_banned_terms(path: Path):
    text = path.read_text(encoding="utf-8", errors="ignore")
    hits = []
    for lineno, line in enumerate(text.splitlines(), 1):
        m = BANNED.search(line)
        if m:
            hits.append(f"line {lineno}: ...{line[max(0, m.start() - 30):m.end() + 30]}...")
    assert not hits, f"banned term in {path.relative_to(REPO)}:\n" + "\n".join(hits[:10])


def test_paths_have_no_banned_terms():
    bad = [p.relative_to(REPO).as_posix() for p in _candidate_files()
           if BANNED.search(p.relative_to(REPO).as_posix())]
    assert not bad
