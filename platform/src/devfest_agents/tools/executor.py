"""Validate arguments and run a registry tool.

SQL tools run as the SELECT-only ``agent_ro`` role, inside a READ ONLY
transaction with a 5 s statement timeout, wrapped in ``LIMIT max_rows+1`` so
truncation can be reported. Every run is logged to ``tools.tool_runs``.

Errors never raise into ADK: they come back as ``{"error": "..."}`` written so
the model can correct its arguments and call again.
"""

from __future__ import annotations

import datetime as dt
import logging
import time
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import psycopg
from psycopg import errors as pg_errors
from psycopg.types.json import Jsonb

from .spec import CoercionError, ParamSpec, ToolSpec, coerce_value
from .sql_guard import SqlGuardError, compile_sql

if TYPE_CHECKING:
    from ..db import Database

logger = logging.getLogger(__name__)

STATEMENT_TIMEOUT = "5s"


class ToolArgError(ValueError):
    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


def validate_args(params: list[ParamSpec], args: dict[str, Any] | None) -> dict[str, Any]:
    """Unknown keys rejected, defaults applied, then required / type / enum / range."""
    args = dict(args or {})
    by_name = {p.name: p for p in params}
    problems: list[str] = []
    unknown = sorted(k for k in args if k not in by_name)
    if unknown:
        allowed = ", ".join(by_name) or "(none)"
        problems.append(f"unknown argument(s): {', '.join(unknown)}; allowed: {allowed}")
    out: dict[str, Any] = {}
    for p in params:
        raw = args.get(p.name)
        if raw is None or (isinstance(raw, str) and raw == "" and p.type != "string"):
            raw = p.default
        if raw is None:
            if p.required:
                problems.append(f"'{p.name}' is required ({p.type}{', e.g. ' + str(p.example) if p.example is not None else ''})")
            out[p.name] = None
            continue
        try:
            val = coerce_value(p.type, raw, name=p.name)
        except CoercionError as exc:
            problems.append(str(exc))
            continue
        if p.enum is not None:
            cmp = val.isoformat() if isinstance(val, dt.date) else val
            if cmp not in p.enum:
                problems.append(f"'{p.name}' must be one of {p.enum} (got {raw!r})")
                continue
        if p.min is not None and val < p.min:
            problems.append(f"'{p.name}' must be >= {_num(p.min)} (got {raw!r})")
            continue
        if p.max is not None and val > p.max:
            problems.append(f"'{p.name}' must be <= {_num(p.max)} (got {raw!r})")
            continue
        out[p.name] = val
    if problems:
        raise ToolArgError(problems)
    return out


def _num(x: float) -> str:
    return str(int(x)) if float(x).is_integer() else str(x)


def json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value if value == value and value not in (float("inf"), float("-inf")) else None
    if isinstance(value, Decimal):
        f = float(value)
        return f if f == f and f not in (float("inf"), float("-inf")) else None
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat()
    if isinstance(value, dt.timedelta):
        return value.total_seconds()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value).hex()
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(v) for v in value]
    return str(value)


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[list[Any]]  # JSON-safe
    truncated: bool
    duration_ms: int
    params: dict[str, Any] = field(default_factory=dict)

    @property
    def row_count(self) -> int:
        return len(self.rows)

    def rows_as_dicts(self) -> list[dict[str, Any]]:
        return [dict(zip(self.columns, r)) for r in self.rows]


class ToolExecutionError(Exception):
    """Raised by run_query; message is safe and model-readable."""


class ToolExecutor:
    def __init__(self, db: "Database", *, max_rows: int = 200, log_runs: bool = True):
        self.db = db
        self.max_rows = max_rows
        self.log_runs = log_runs

    # -- low level ---------------------------------------------------------------
    async def run_query(self, spec: ToolSpec, values: dict[str, Any]) -> QueryResult:
        try:
            compiled = compile_sql(spec.sql or "", spec.param_types)
        except SqlGuardError as exc:
            raise ToolExecutionError(str(exc)) from exc
        return await self.execute(compiled, values)

    async def execute(self, compiled: str, values: dict[str, Any]) -> QueryResult:
        """Run compiled SQL (psycopg ``%(name)s`` placeholders) as agent_ro, read-only."""
        wrapped = f"SELECT * FROM (\n{compiled}\n) AS q LIMIT {int(self.max_rows) + 1}"
        await self.db.ensure_open()
        started = time.perf_counter()
        try:
            async with self.db.agent_pool.connection(timeout=10.0) as conn:
                async with conn.transaction():
                    await conn.execute("SET TRANSACTION READ ONLY")
                    await conn.execute(f"SET LOCAL statement_timeout = '{STATEMENT_TIMEOUT}'")
                    cur = await conn.execute(wrapped, values)
                    columns = [d.name for d in (cur.description or [])]
                    raw_rows = await cur.fetchall()
        except pg_errors.QueryCanceled as exc:
            raise ToolExecutionError(
                f"The query was cancelled after {STATEMENT_TIMEOUT} (statement timeout). "
                "Use a narrower date range or more selective filters."
            ) from exc
        except psycopg.Error as exc:
            diag = getattr(exc, "diag", None)
            msg = (diag.message_primary if diag and diag.message_primary else str(exc)).strip()
            raise ToolExecutionError(f"Database error: {msg}") from exc
        except Exception as exc:  # pool timeout, connection refused, ...
            raise ToolExecutionError(f"Database unavailable ({type(exc).__name__}). Try again shortly.") from exc
        duration = int((time.perf_counter() - started) * 1000)
        truncated = len(raw_rows) > self.max_rows
        rows = [[json_safe(v) for v in r] for r in raw_rows[: self.max_rows]]
        return QueryResult(columns=columns, rows=rows, truncated=truncated, duration_ms=duration)

    # -- what the LLM tool calls ---------------------------------------------------
    async def run_tool(self, spec: ToolSpec, args: dict[str, Any] | None) -> dict[str, Any]:
        started = time.perf_counter()
        if spec.tool_type == "factual":
            await self._log(spec, {}, None, started, None)
            return {"answer": spec.answer, "source": spec.source or "Nimbus Markets internal reference"}

        try:
            values = validate_args(spec.params, args)
        except ToolArgError as exc:
            message = (
                f"Invalid arguments for {spec.name}: {exc}. "
                f"Expected parameters: {_describe_params(spec.params)}. Fix the arguments and call the tool again."
            )
            await self._log(spec, args or {}, None, started, message)
            return {"error": message}

        try:
            result = await self.run_query(spec, values)
        except ToolExecutionError as exc:
            message = f"{spec.name} failed: {exc}"
            await self._log(spec, values, None, started, message)
            return {"error": message}

        await self._log(spec, values, result.row_count, started, None)
        shown = {k: json_safe(v) for k, v in values.items()}
        return {
            "tool": spec.name,
            "params": shown,
            "row_count": result.row_count,
            "truncated": result.truncated,
            "columns": result.columns,
            "rows": result.rows_as_dicts(),
            "summary": _summary(spec, result),
        }

    async def _log(self, spec: ToolSpec, args: dict[str, Any], row_count: int | None, started: float,
                   error: str | None) -> None:
        if not self.log_runs:
            return
        duration = int((time.perf_counter() - started) * 1000)
        try:
            async with self.db.app_pool.connection(timeout=3.0) as conn:
                await conn.execute(
                    "INSERT INTO tools.tool_runs (name, agent, args, row_count, duration_ms, error) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (spec.name, spec.agent, Jsonb(json_safe(args)), row_count, duration, error),
                )
        except Exception as exc:  # noqa: BLE001 - logging must never fail a tool call
            logger.warning("Could not log tool run for %s: %s", spec.name, type(exc).__name__)


def _describe_params(params: list[ParamSpec]) -> str:
    if not params:
        return "(none)"
    parts = []
    for p in params:
        bits = [p.type]
        if p.required:
            bits.append("required")
        if p.enum:
            bits.append("one of " + "/".join(map(str, p.enum)))
        if p.default is not None:
            bits.append(f"default {p.default}")
        parts.append(f"{p.name} ({', '.join(bits)})")
    return ", ".join(parts)


def _summary(spec: ToolSpec, result: QueryResult) -> str:
    if result.row_count == 0:
        return (f"{spec.name} returned no rows for these arguments. Say so plainly; "
                "do not invent numbers. Consider a different date range.")
    text = f"{spec.name} returned {result.row_count} row(s) with columns: {', '.join(result.columns)}."
    if result.truncated:
        text += (f" Output was truncated to the first {result.row_count} rows; "
                 "mention this and suggest narrower filters if totals matter.")
    return text
