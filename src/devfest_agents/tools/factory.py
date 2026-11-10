"""ToolSpec -> ADK FunctionTool.

ADK builds the function declaration the LLM sees from a Python function's
signature, type annotations and docstring. Registry tools are rows, not code,
so we *generate* such a function per row: an ``async def tool(**kwargs)`` whose
``__signature__``, ``__annotations__``, ``__name__`` and ``__doc__`` are set from
the spec. FunctionTool then introspects it exactly like a hand-written tool.
"""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from typing import Annotated, Any, Literal, Optional

from google.adk.tools import FunctionTool
from pydantic import Field

from .spec import ParamSpec, ToolSpec

PY_TYPES: dict[str, type] = {"date": str, "string": str, "integer": int, "number": float, "boolean": bool}

ToolRunner = Callable[[ToolSpec, dict[str, Any]], Awaitable[dict[str, Any]]]


class RegistryTool(FunctionTool):
    """A FunctionTool generated from a registry row (keeps the spec for tracing)."""

    def __init__(self, func: Callable[..., Any], spec: ToolSpec):
        super().__init__(func)
        self.spec = spec
        self.tool_type = spec.tool_type
        self.agent_schema = spec.agent


def _param_description(p: ParamSpec) -> str:
    text = p.description.strip()
    if p.type == "date" and "YYYY-MM-DD" not in text:
        text = (text + " " if text else "") + "(date, YYYY-MM-DD)"
    if p.example is not None:
        text = (text + " " if text else "") + f"Example: {p.example}."
    if not p.required and p.default is None:
        text = (text + " " if text else "") + "Optional; omit for no filter."
    return text.strip()


def _annotation(p: ParamSpec) -> Any:
    base: Any = PY_TYPES[p.type]
    if p.enum:
        base = Literal[tuple(p.enum)]  # type: ignore[valid-type]
    constraints: dict[str, Any] = {"description": _param_description(p)}
    if p.min is not None:
        constraints["ge"] = int(p.min) if p.type == "integer" else p.min
    if p.max is not None:
        constraints["le"] = int(p.max) if p.type == "integer" else p.max
    if not p.required and p.default is None:
        base = Optional[base]
    return Annotated[base, Field(**constraints)]


def render_docstring(spec: ToolSpec) -> str:
    doc = f"{spec.title}.\n\n{spec.description.strip()}" if not spec.description.startswith(spec.title) \
        else spec.description.strip()
    if spec.tool_type == "factual":
        doc += "\n\nReturns a curated answer with its source. Takes no arguments."
    return doc


def build_function(spec: ToolSpec, runner: ToolRunner) -> Callable[..., Awaitable[dict[str, Any]]]:
    """Generate the async function ADK will wrap."""

    async def _tool(**kwargs: Any) -> dict[str, Any]:
        return await runner(spec, kwargs)

    parameters: list[inspect.Parameter] = []
    annotations: dict[str, Any] = {}
    # Required first only for readability; keyword-only params can be in any order.
    for p in sorted(spec.params, key=lambda x: not x.required):
        ann = _annotation(p)
        default = inspect.Parameter.empty if p.required else p.default
        parameters.append(inspect.Parameter(p.name, inspect.Parameter.KEYWORD_ONLY, default=default, annotation=ann))
        annotations[p.name] = ann
    annotations["return"] = dict
    _tool.__signature__ = inspect.Signature(parameters, return_annotation=dict)  # type: ignore[attr-defined]
    _tool.__annotations__ = annotations
    _tool.__name__ = spec.name
    _tool.__qualname__ = spec.name
    _tool.__doc__ = render_docstring(spec)
    return _tool


def build_tool(spec: ToolSpec, runner: ToolRunner) -> RegistryTool:
    return RegistryTool(build_function(spec, runner), spec)


async def _never_run(spec: ToolSpec, kwargs: dict[str, Any]) -> dict[str, Any]:  # pragma: no cover
    return {"error": "declaration-only tool"}


def declaration_json(spec: ToolSpec) -> dict[str, Any]:
    """The FunctionDeclaration ADK sends to the model, as plain JSON
    (``name``, ``description``, ``parameters``). Used by POST /api/tools/test."""
    decl = build_tool(spec, _never_run)._get_declaration()
    assert decl is not None
    dumped = decl.model_dump(mode="json", exclude_none=True)
    parameters = dumped.get("parameters_json_schema") or dumped.get("parameters") or {"type": "object", "properties": {}}
    return {"name": dumped.get("name", spec.name), "description": dumped.get("description", ""), "parameters": parameters}
