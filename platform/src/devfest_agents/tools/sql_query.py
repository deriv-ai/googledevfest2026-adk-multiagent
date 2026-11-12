"""run_sql(): read-only SQL for hand-written Python tools (e.g. the marketing agent).

Same safety as registry tools: the SQL guard, the SELECT-only agent_ro role, a
READ ONLY transaction, a 5 s timeout and a row cap. Problems come back as
``{"error": "..."}`` so the model can read them and try again.

    await run_sql("marketing", "SELECT ... WHERE s.spend_date >= :start_date", start_date="2026-07-01")
"""

from __future__ import annotations

from typing import Any

from ..services import get_services
from .executor import ToolExecutionError
from .sql_guard import check_sql, compile_untyped_sql, find_placeholders


async def run_sql(schema: str, sql: str, **params: Any) -> dict[str, Any]:
    problems = check_sql(sql, schema)
    missing = [name for name in find_placeholders(sql) if name not in params]
    if missing:
        problems.append("No value passed for " + ", ".join(f":{name}" for name in missing))
    if problems:
        return {"error": "; ".join(problems)}
    try:
        result = await get_services().tool_executor().execute(compile_untyped_sql(sql), params)
    except ToolExecutionError as exc:
        return {"error": str(exc)}
    return {"row_count": result.row_count, "truncated": result.truncated, "rows": result.rows_as_dicts()}
