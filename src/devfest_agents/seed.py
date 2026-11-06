"""Seed starter tools from YAML into tools.tools.

    python -m devfest_agents.seed            # insert missing tools only
    python -m devfest_agents.seed --force    # overwrite starter tools from the YAML

Each entry is validated with the same ToolSpec + SQL guard the UI uses.
The app also calls ``seed_tools()`` at startup (insert-if-missing), so edits
made in the UI are never overwritten.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Any

import yaml

from .tools.spec import ToolSpec, lint_tool

logger = logging.getLogger(__name__)


def load_starter_specs(path: str | Path) -> tuple[list[ToolSpec], list[str]]:
    """Parse + validate the YAML. Returns (valid specs, error messages)."""
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    entries: list[Any] = data.get("tools", []) if isinstance(data, dict) else data
    specs: list[ToolSpec] = []
    errors: list[str] = []
    for i, entry in enumerate(entries or []):
        label = entry.get("name", f"#{i}") if isinstance(entry, dict) else f"#{i}"
        if not isinstance(entry, dict):
            errors.append(f"{label}: entry must be a mapping")
            continue
        spec, problems = lint_tool(entry)
        if problems or spec is None:
            errors.extend(f"{label}: {p}" for p in problems)
            continue
        specs.append(spec)
    return specs, errors


async def seed_tools(repo, path: str | Path | None, *, force: bool = False) -> dict[str, Any]:
    """Insert (or with force, overwrite) starter tools. Never raises on bad entries."""
    summary: dict[str, Any] = {"inserted": [], "updated": [], "skipped": [], "errors": []}
    if path is None or not Path(path).exists():
        summary["errors"].append(f"starter tools file not found: {path}")
        logger.warning("Starter tools file not found (%s); skipping seed", path)
        return summary
    specs, errors = load_starter_specs(path)
    summary["errors"].extend(errors)
    for msg in errors:
        logger.warning("Invalid starter tool: %s", msg)
    for spec in specs:
        outcome = await repo.upsert_seed(spec, force=force)
        summary[outcome].append(spec.name)
    logger.info("Starter tools: %d inserted, %d updated, %d already present, %d invalid",
                len(summary["inserted"]), len(summary["updated"]), len(summary["skipped"]), len(errors))
    return summary


async def _main(force: bool, path: str | None) -> int:
    from .config import get_settings
    from .db import Database
    from .tools.registry import ToolRepository

    settings = get_settings()
    db = Database.from_settings(settings)
    try:
        if not await db.open(attempts=10):
            print("database not reachable", file=sys.stderr)
            return 2
        target = Path(path) if path else settings.resolved_starter_tools_path
        summary = await seed_tools(ToolRepository(db), target, force=force)
    finally:
        await db.close()
    for key in ("inserted", "updated", "skipped"):
        print(f"{key}: {', '.join(summary[key]) or '-'}")
    for err in summary["errors"]:
        print(f"error: {err}", file=sys.stderr)
    return 1 if summary["errors"] else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed starter tools into tools.tools")
    parser.add_argument("--force", action="store_true", help="overwrite existing starter tools from the YAML")
    parser.add_argument("--path", help="YAML file (default: STARTER_TOOLS_PATH)")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    return asyncio.run(_main(args.force, args.path))


if __name__ == "__main__":
    raise SystemExit(main())
