"""SQL safety checks and `:name` -> psycopg placeholder conversion.

This is defence in depth. The real enforcement is that tool SQL runs as the
SELECT-only ``agent_ro`` role inside a READ ONLY transaction with a statement
timeout. The guard gives tool authors fast, readable feedback in the UI:

* exactly one SELECT / WITH statement (one trailing ``;`` is tolerated);
* no DDL / DML / session keywords;
* only the tool's own agent schema (``finance.`` or ``trading.``); never
  ``tools.``, ``pg_*``, ``information_schema`` or the other agent's schema;
* tables in FROM / JOIN must be schema-qualified (CTE names excepted).

String literals, quoted identifiers and comments are masked before any check,
so ``'HH24:MI'`` is not a placeholder and ``'drop'`` is not a keyword.
"""

from __future__ import annotations

import re
from collections.abc import Mapping

PLACEHOLDER_RE = re.compile(r"(?<!:):([a-zA-Z_][a-zA-Z0-9_]*)")

AGENT_SCHEMAS = {"finance", "trading"}
KNOWN_SCHEMAS = AGENT_SCHEMAS | {"tools", "public", "information_schema", "pg_catalog", "pg_toast"}

# Postgres type each param type is bound as. Explicit casts make NULL optional
# params type-check (`%(entity_id)s::text IS NULL`).
PG_CAST = {
    "date": "date",
    "string": "text",
    "integer": "bigint",
    "number": "numeric",
    "boolean": "boolean",
}

# Whole-word keywords that never belong in a read-only report query. Words that
# are also plausible column names (close, open, comment, ...) are deliberately
# not listed; the READ ONLY transaction + SELECT-only role cover those.
FORBIDDEN_KEYWORDS = (
    "insert", "update", "delete", "merge", "drop", "create", "alter", "truncate",
    "grant", "revoke", "copy", "vacuum", "analyze", "analyse", "cluster", "reindex", "refresh",
    "security", "call", "do", "execute", "prepare", "deallocate", "listen", "notify",
    "unlisten", "lock", "set", "reset", "discard", "into", "explain", "checkpoint",
    "begin", "commit", "rollback", "savepoint",
)
FORBIDDEN_FUNCTIONS = ("set_config", "current_setting", "dblink", "lo_import", "lo_export", "lo_get", "lo_put")

_FORBIDDEN_RE = re.compile(r"\b(" + "|".join(FORBIDDEN_KEYWORDS) + r")\b", re.IGNORECASE)
_FORBIDDEN_FN_RE = re.compile(r"\b(" + "|".join(FORBIDDEN_FUNCTIONS) + r")\s*\(", re.IGNORECASE)
_IDENT = r"[a-zA-Z_][a-zA-Z0-9_$]*"
_QUALIFIED_RE = re.compile(rf"\b({_IDENT})\s*\.\s*({_IDENT}|\")")
_PG_WORD_RE = re.compile(r"\b(pg_[a-zA-Z0-9_]*|information_schema)\b", re.IGNORECASE)
_FROM_JOIN_RE = re.compile(rf"\b(from|join)\s+(lateral\s+)?({_IDENT})(\s*\.\s*{_IDENT})?(\s*\()?", re.IGNORECASE)
_CTE_RE = re.compile(rf"(?:\bwith\s+(?:recursive\s+)?|,\s*)({_IDENT})\s*(?:\([^)]*\)\s*)?as\s+(?:not\s+)?(?:materialized\s+)?\(",
                     re.IGNORECASE)
# FROM inside these function calls is not a table reference: extract(month FROM x)
_FROM_FUNCTIONS = {"extract", "substring", "trim", "overlay", "position", "substr", "btrim", "ltrim", "rtrim"}


class SqlGuardError(ValueError):
    """Raised by compile_sql when the SQL cannot be compiled."""


# ---------------------------------------------------------------------------
# Lexical masking
# ---------------------------------------------------------------------------
def mask_sql(sql: str) -> str:
    """Return ``sql`` with the *contents* of string literals, quoted identifiers,
    dollar-quoted strings and comments replaced by spaces (same length, so
    offsets line up with the original). Delimiters of literals are kept."""
    out = list(sql)
    i, n = 0, len(sql)

    def blank(a: int, b: int) -> None:
        for k in range(a, b):
            if out[k] != "\n":
                out[k] = " "

    while i < n:
        ch = sql[i]
        nxt = sql[i + 1] if i + 1 < n else ""
        if ch == "-" and nxt == "-":
            end = sql.find("\n", i)
            end = n if end == -1 else end
            blank(i, end)
            i = end
        elif ch == "/" and nxt == "*":
            depth, j = 1, i + 2
            while j < n and depth:
                if sql.startswith("/*", j):
                    depth, j = depth + 1, j + 2
                elif sql.startswith("*/", j):
                    depth, j = depth - 1, j + 2
                else:
                    j += 1
            blank(i, j)
            i = j
        elif ch in ("'", '"'):
            j = i + 1
            while j < n:
                if sql[j] == ch:
                    if j + 1 < n and sql[j + 1] == ch:  # doubled quote escape
                        j += 2
                        continue
                    break
                if ch == "'" and sql[j] == "\\" and i > 0 and sql[i - 1] in "eE":
                    j += 2
                    continue
                j += 1
            blank(i + 1, min(j, n))
            i = j + 1
        elif ch == "$":
            m = re.match(r"\$([a-zA-Z_][a-zA-Z0-9_]*)?\$", sql[i:])
            if m and (i == 0 or not (sql[i - 1].isalnum() or sql[i - 1] == "_")):
                tag = m.group(0)
                end = sql.find(tag, i + len(tag))
                end = n if end == -1 else end
                blank(i + len(tag), end)
                i = end + len(tag)
            else:
                i += 1
        else:
            i += 1
    return "".join(out)


def find_placeholders(sql: str) -> list[str]:
    """Distinct ``:name`` placeholders in order of first appearance, ignoring
    ``::casts`` and anything inside literals or comments."""
    seen: list[str] = []
    for m in PLACEHOLDER_RE.finditer(mask_sql(sql)):
        if m.group(1) not in seen:
            seen.append(m.group(1))
    return seen


def _strip_statement(sql: str) -> tuple[str, str]:
    """(original, masked) with surrounding whitespace and one trailing ';' removed."""
    masked = mask_sql(sql)
    stripped = masked.rstrip()
    if stripped.endswith(";"):
        stripped = stripped[:-1].rstrip()
    end = len(stripped)
    start = len(stripped) - len(stripped.lstrip())
    return sql[start:end], masked[start:end]


def normalize_sql(sql: str) -> str:
    """The statement without trailing ``;`` (needed for the LIMIT wrapper)."""
    return _strip_statement(sql)[0]


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------
def _enclosing_function(masked: str, pos: int) -> str | None:
    """Name of the function whose parentheses enclose ``pos`` (or None)."""
    depth = 0
    for k in range(pos - 1, -1, -1):
        c = masked[k]
        if c == ")":
            depth += 1
        elif c == "(":
            if depth == 0:
                m = re.search(rf"({_IDENT})\s*$", masked[:k])
                return m.group(1).lower() if m else None
            depth -= 1
    return None


def check_sql(sql: str, agent: str) -> list[str]:
    """Return a list of human-readable problems (empty list = OK)."""
    errors: list[str] = []
    if agent not in AGENT_SCHEMAS:
        return [f"agent must be one of {sorted(AGENT_SCHEMAS)}"]
    if not sql or not sql.strip():
        return ["SQL is empty"]

    _, masked = _strip_statement(sql)
    if not masked.strip():
        return ["SQL is empty"]

    if ";" in masked:
        errors.append("Only a single statement is allowed (found ';' before the end of the query)")

    first = re.match(r"\s*\(*\s*([a-zA-Z]+)", masked)
    if not first or first.group(1).lower() not in ("select", "with"):
        errors.append("Query must start with SELECT or WITH")

    bad_kw = sorted({m.group(1).upper() for m in _FORBIDDEN_RE.finditer(masked)})
    if bad_kw:
        errors.append(f"Forbidden keyword(s): {', '.join(bad_kw)} (tools are read-only SELECT queries)")
    bad_fn = sorted({m.group(1).lower() for m in _FORBIDDEN_FN_RE.finditer(masked)})
    if bad_fn:
        errors.append(f"Forbidden function(s): {', '.join(bad_fn)}")

    pg_words = sorted({m.group(1).lower() for m in _PG_WORD_RE.finditer(masked)})
    if pg_words:
        errors.append(f"System catalogs are not allowed: {', '.join(pg_words)}")

    other = sorted(
        {
            m.group(1).lower()
            for m in _QUALIFIED_RE.finditer(masked)
            if m.group(1).lower() in KNOWN_SCHEMAS and m.group(1).lower() != agent
            and not m.group(1).lower().startswith("pg_") and m.group(1).lower() != "information_schema"
        }
    )
    if other:
        errors.append(
            f"A {agent} tool may only read the '{agent}' schema; found reference(s) to: "
            + ", ".join(f"{s}." for s in other)
        )

    ctes = {m.group(1).lower() for m in _CTE_RE.finditer(masked)}
    unqualified: list[str] = []
    for m in _FROM_JOIN_RE.finditer(masked):
        name, qualifier, call = m.group(3), m.group(4), m.group(5)
        if qualifier or call:  # schema.table, or a set-returning function call
            continue
        if name.lower() in ctes or name.lower() in ("select", "lateral", "unnest", "only"):
            continue
        if m.group(1).lower() == "from":
            if re.search(r"\bdistinct\s*$", masked[:m.start()], re.IGNORECASE):
                continue  # a IS DISTINCT FROM b
            if _enclosing_function(masked, m.start()) in _FROM_FUNCTIONS:
                continue  # extract(month FROM x)
        if name not in unqualified:
            unqualified.append(name)
    if unqualified:
        errors.append(
            "Tables must be schema-qualified: "
            + ", ".join(f"{t} -> {agent}.{t}" for t in unqualified)
        )
    return errors


# ---------------------------------------------------------------------------
# Compilation
# ---------------------------------------------------------------------------
def compile_sql(sql: str, param_types: Mapping[str, str]) -> str:
    """Convert ``:name`` to ``%(name)s::<pgtype>`` and escape literal ``%``.

    ``param_types`` maps param name -> ToolSpec type (date|string|integer|number|boolean).
    Raises SqlGuardError if a placeholder has no declared type.
    """
    original, masked = _strip_statement(sql)
    out: list[str] = []
    pos = 0
    for m in PLACEHOLDER_RE.finditer(masked):
        name = m.group(1)
        if name not in param_types:
            raise SqlGuardError(f"Placeholder :{name} has no declared parameter")
        out.append(original[pos:m.start()].replace("%", "%%"))
        cast = PG_CAST.get(param_types[name], "text")
        out.append(f"%({name})s::{cast}")
        pos = m.end()
    out.append(original[pos:].replace("%", "%%"))
    return "".join(out)
