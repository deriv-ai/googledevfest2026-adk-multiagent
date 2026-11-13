"""Tool specification: the shape shared by seed/starter_tools.yaml, the tools API
and the tools.tools table.

Two tool types:
* ``sql``     a parameterised SELECT over the agent's own schema; one typed
              argument per ``:placeholder``.
* ``factual`` a curated fixed answer (definitions, policies); no arguments.
"""

from __future__ import annotations

import datetime as dt
import keyword
import math
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from . import sql_guard

ParamType = Literal["date", "string", "integer", "number", "boolean"]
AgentName = Literal["finance", "trading"]
ToolType = Literal["sql", "factual"]

TOOL_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{2,63}$")
PARAM_NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
RESERVED_PARAM_NAMES = {"tool_context", "input_stream", "self", "kwargs", "args"}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Titles and descriptions are written by workshop participants and end up in LLM prompts
# (titles in the orchestrator's catalogue, descriptions as function descriptions), so keep
# them bounded. Limits sit well above the starter tools (title 74, description 863 chars).
TITLE_MAX = 200
DESCRIPTION_MAX = 2000
PARAM_DESCRIPTION_MAX = 500


class CoercionError(ValueError):
    pass


def coerce_value(ptype: str, value: Any, *, name: str = "value") -> Any:
    """Coerce a JSON-ish value to the Python value bound for ``ptype``.

    Dates must be ISO ``YYYY-MM-DD``; the error text is written for an LLM to
    read and retry with a corrected value.
    """
    if value is None:
        return None
    if ptype == "date":
        if isinstance(value, dt.datetime):
            return value.date()
        if isinstance(value, dt.date):
            return value
        if isinstance(value, str):
            text = value.strip()
            if DATE_RE.match(text):
                try:
                    return dt.date.fromisoformat(text)
                except ValueError:
                    pass
        raise CoercionError(f"'{name}' must be a date in YYYY-MM-DD format, e.g. 2026-07-01 (got {value!r})")
    if ptype == "integer":
        if isinstance(value, bool):
            raise CoercionError(f"'{name}' must be an integer (got {value!r})")
        if isinstance(value, int):
            return value
        if isinstance(value, float) and value.is_integer():
            return int(value)
        if isinstance(value, str) and re.fullmatch(r"\s*-?\d+\s*", value):
            return int(value)
        raise CoercionError(f"'{name}' must be an integer (got {value!r})")
    if ptype == "number":
        if isinstance(value, bool):
            raise CoercionError(f"'{name}' must be a number (got {value!r})")
        if isinstance(value, (int, float)):
            if isinstance(value, float) and not math.isfinite(value):
                raise CoercionError(f"'{name}' must be a finite number (got {value!r})")
            return float(value)
        if isinstance(value, str):
            try:
                out = float(value.strip())
            except ValueError:
                pass
            else:
                if math.isfinite(out):
                    return out
        raise CoercionError(f"'{name}' must be a number (got {value!r})")
    if ptype == "boolean":
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.strip().lower() in ("true", "false"):
            return value.strip().lower() == "true"
        if isinstance(value, int) and value in (0, 1):
            return bool(value)
        raise CoercionError(f"'{name}' must be true or false (got {value!r})")
    if ptype == "string":
        if isinstance(value, (dict, list)):
            raise CoercionError(f"'{name}' must be a string (got {type(value).__name__})")
        return value if isinstance(value, str) else str(value)
    raise CoercionError(f"unknown parameter type {ptype!r}")


def to_jsonable(value: Any) -> Any:
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    return value


class ParamSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    type: ParamType = "string"
    required: bool = False
    description: str = Field(default="", max_length=PARAM_DESCRIPTION_MAX)
    default: Any = None
    example: Any = None
    enum: list[Any] | None = None
    min: float | None = None
    max: float | None = None

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        if not PARAM_NAME_RE.match(v):
            raise ValueError(f"parameter name {v!r} must match {PARAM_NAME_RE.pattern}")
        if keyword.iskeyword(v) or v in RESERVED_PARAM_NAMES:
            raise ValueError(f"parameter name {v!r} is reserved")
        return v

    @field_validator("enum")
    @classmethod
    def _enum(cls, v):
        if v is not None and len(v) == 0:
            return None
        return v

    @model_validator(mode="after")
    def _values(self) -> "ParamSpec":
        if self.enum is not None:
            self.enum = [coerce_value(self.type, e, name=f"{self.name}.enum") for e in self.enum]
            if self.type == "boolean":
                raise ValueError(f"parameter {self.name!r}: enum is not supported for boolean")
            self.enum = [to_jsonable(e) for e in self.enum]
        for attr in ("default", "example"):
            raw = getattr(self, attr)
            if raw is None or raw == "":
                setattr(self, attr, None)
                continue
            val = coerce_value(self.type, raw, name=f"{self.name}.{attr}")
            if self.enum is not None and to_jsonable(val) not in self.enum:
                raise ValueError(f"parameter {self.name!r}: {attr} {raw!r} is not one of {self.enum}")
            setattr(self, attr, to_jsonable(val))
        if (self.min is not None or self.max is not None) and self.type not in ("integer", "number"):
            raise ValueError(f"parameter {self.name!r}: min/max only apply to integer or number")
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError(f"parameter {self.name!r}: min is greater than max")
        if self.required and self.default is not None:
            raise ValueError(f"parameter {self.name!r}: a required parameter cannot have a default "
                             "(use example for test values, or make it optional)")
        return self

    def as_dict(self) -> dict[str, Any]:
        return self.model_dump(exclude_none=False)


class ToolSpec(BaseModel):
    """One registry tool. JSON keys match the YAML: ``sql``, ``answer``, ``source``."""

    model_config = ConfigDict(extra="ignore")

    name: str
    agent: AgentName
    tool_type: ToolType = "sql"
    title: str = Field(min_length=1, max_length=TITLE_MAX)
    description: str = Field(min_length=1, max_length=DESCRIPTION_MAX)
    params: list[ParamSpec] = Field(default_factory=list)
    sql: str | None = None
    answer: str | None = None
    source: str | None = None
    enabled: bool = True

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        if not TOOL_NAME_RE.match(v or ""):
            raise ValueError("name must be 3-64 chars of lowercase letters, digits and _, starting with a letter")
        return v

    @field_validator("title", "description")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("must not be empty")
        return v

    @field_validator("title")
    @classmethod
    def _one_line(cls, v: str) -> str:
        if any(ch in v for ch in "\r\n") or any(ord(ch) < 32 or ord(ch) == 127 for ch in v):
            raise ValueError("must be a single line without control characters")
        return v

    @field_validator("sql", "answer", "source", mode="before")
    @classmethod
    def _blank(cls, v):
        if isinstance(v, str) and not v.strip():
            return None
        return v

    @field_validator("params", mode="before")
    @classmethod
    def _params_none(cls, v):
        return [] if v is None else v

    @model_validator(mode="after")
    def _per_type(self) -> "ToolSpec":
        names = [p.name for p in self.params]
        dupes = sorted({n for n in names if names.count(n) > 1})
        if dupes:
            raise ValueError(f"duplicate parameter name(s): {', '.join(dupes)}")
        if self.tool_type == "sql":
            if not self.sql:
                raise ValueError("sql tools need a 'sql' query")
            placeholders = sql_guard.find_placeholders(self.sql)
            missing = [p for p in placeholders if p not in names]
            unused = [n for n in names if n not in placeholders]
            problems = []
            if missing:
                problems.append("placeholder(s) without a declared parameter: " + ", ".join(f":{p}" for p in missing))
            if unused:
                problems.append("declared parameter(s) not used in the SQL: " + ", ".join(unused))
            if problems:
                raise ValueError("; ".join(problems))
            self.answer = None
            self.source = None
        else:
            if not self.answer:
                raise ValueError("factual tools need an 'answer'")
            if self.params:
                raise ValueError("factual tools take no parameters")
            self.sql = None
        return self

    @property
    def param_types(self) -> dict[str, str]:
        return {p.name: p.type for p in self.params}

    def to_api(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "agent": self.agent,
            "tool_type": self.tool_type,
            "title": self.title,
            "description": self.description,
            "enabled": self.enabled,
            "params": [p.as_dict() for p in self.params],
            "sql": self.sql,
            "answer": self.answer,
            "source": self.source,
        }


def _format_pydantic_errors(exc: ValidationError) -> list[str]:
    out = []
    for err in exc.errors():
        loc = ".".join(str(x) for x in err.get("loc", ()) if x != "__root__")
        msg = err.get("msg", "invalid")
        msg = msg.removeprefix("Value error, ")
        out.append(f"{loc}: {msg}" if loc else msg)
    return out


def lint_tool(data: dict[str, Any] | ToolSpec) -> tuple[ToolSpec | None, list[str]]:
    """Parse + validate a tool exactly as the seeder and the UI do.

    Returns ``(spec, [])`` when valid, else ``(spec_or_None, errors)``.
    """
    if isinstance(data, ToolSpec):
        spec = data
    else:
        try:
            spec = ToolSpec.model_validate(data)
        except ValidationError as exc:
            return None, _format_pydantic_errors(exc)
    if spec.tool_type == "sql":
        errors = sql_guard.check_sql(spec.sql or "", spec.agent)
        if errors:
            return spec, errors
    return spec, []
