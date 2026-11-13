"""The competition leaderboard: leaderboard.json and a self-contained leaderboard.html.

The page reloads itself every 15 seconds, so it can stay on the projector while
the judge works through the submissions.
"""

from __future__ import annotations

import html
import json
import time
from pathlib import Path
from typing import Any


def ranked(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Highest score first; on a tie, the earlier submission wins."""
    return sorted(results, key=lambda r: (-r["score"], r.get("submitted_at") or "~", r["name"].lower()))


def write_leaderboard(results: list[dict[str, Any]], out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    rows = ranked(results)
    (out / "leaderboard.json").write_text(json.dumps(rows, indent=2))
    (out / "leaderboard.html").write_text(render(rows))


def render(rows: list[dict[str, Any]]) -> str:
    kinds = sorted({kind for r in rows for kind in r.get("by_kind", {})})
    head = "".join(f"<th class=kind>{html.escape(k)}</th>" for k in kinds)
    body = "\n".join(render_row(rank, r, kinds) for rank, r in enumerate(rows, 1))
    empty = "" if rows else f"<tr><td colspan={4 + len(kinds)} class=empty>No submissions judged yet.</td></tr>"
    return PAGE.format(head=head, body=body or empty, updated=time.strftime("%H:%M:%S"), count=len(rows))


def render_row(rank: int, r: dict[str, Any], kinds: list[str]) -> str:
    share = r["score"] / r["max_score"] if r["max_score"] else 0
    cells = "".join(f"<td class=kind>{'/'.join(map(str, r['by_kind'][k])) if k in r.get('by_kind', {}) else '–'}</td>"
                    for k in kinds)
    note = f"<div class=note>{html.escape(r['error'].splitlines()[0][:120])}</div>" if r.get("error") else ""
    version = html.escape((r.get("version") or "")[:7])
    return (f"<tr><td class=rank>{rank}</td>"
            f"<td><div class=name>{html.escape(r['name'])}</div>{note}</td>"
            f"<td class=score><span>{r['score']}</span><small>/{r['max_score']}</small>"
            f"<div class=bar><i style='width:{share:.0%}'></i></div></td>{cells}"
            f"<td class=version>{version}</td></tr>")


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="15">
<title>Leaderboard</title>
<style>
  :root {{ --bg: #f7f8fa; --card: #fff; --ink: #14161c; --muted: #646b7a; --line: #e4e7ec; --accent: #6d4ae8; }}
  @media (prefers-color-scheme: dark) {{
    :root {{ --bg: #0d0f14; --card: #151821; --ink: #eef0f5; --muted: #9aa1b2; --line: #262b36; --accent: #a78bfa; }}
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; background: var(--bg); color: var(--ink);
         font: 18px/1.4 ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif; }}
  main {{ max-width: 1100px; margin: 0 auto; padding: 40px 16px; }}
  header {{ display: flex; justify-content: space-between; align-items: baseline; gap: 16px; flex-wrap: wrap; }}
  h1 {{ margin: 0; font-size: 40px; letter-spacing: -0.02em; }}
  header p {{ margin: 0; color: var(--muted); font-size: 15px; }}
  .table {{ margin-top: 24px; background: var(--card); border: 1px solid var(--line); border-radius: 16px;
           overflow-x: auto; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th {{ text-align: left; font-size: 13px; font-weight: 600; color: var(--muted); text-transform: uppercase;
       letter-spacing: 0.04em; padding: 14px 16px; border-bottom: 1px solid var(--line); }}
  td {{ padding: 14px 16px; border-bottom: 1px solid var(--line); vertical-align: middle; }}
  tr:last-child td {{ border-bottom: 0; }}
  .rank {{ width: 56px; font-size: 22px; font-weight: 700; color: var(--muted); font-variant-numeric: tabular-nums; }}
  tbody tr:nth-child(-n+3) .rank {{ color: var(--accent); }}
  .name {{ font-size: 22px; font-weight: 600; }}
  .note {{ margin-top: 2px; font-size: 13px; color: #d14343; }}
  .score {{ width: 180px; white-space: nowrap; font-variant-numeric: tabular-nums; }}
  .score span {{ font-size: 28px; font-weight: 700; }}
  .score small {{ color: var(--muted); margin-left: 2px; }}
  .bar {{ height: 6px; margin-top: 6px; border-radius: 3px; background: var(--line); overflow: hidden; }}
  .bar i {{ display: block; height: 100%; background: var(--accent); }}
  .kind {{ font-size: 15px; color: var(--muted); white-space: nowrap; font-variant-numeric: tabular-nums; }}
  .version {{ font: 13px ui-monospace, SFMono-Regular, monospace; color: var(--muted); }}
  .empty {{ text-align: center; color: var(--muted); padding: 48px; }}
</style>
</head>
<body>
<main>
  <header>
    <h1>Leaderboard</h1>
    <p>{count} judged · updated {updated} · refreshes every 15 s</p>
  </header>
  <div class="table">
    <table>
      <thead><tr><th>#</th><th>Name</th><th>Score</th>{head}<th>Version</th></tr></thead>
      <tbody>
{body}
      </tbody>
    </table>
  </div>
</main>
</body>
</html>
"""
