"""Tools CRUD + test run. Body keys follow the YAML spec (`sql`, `answer`, `source`)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import JSONResponse

from ..tools.executor import ToolArgError, ToolExecutionError, validate_args
from ..tools.factory import declaration_json
from ..tools.registry import ToolExistsError, ToolNotFoundError
from ..tools.spec import ToolSpec, lint_tool
from . import deps

router = APIRouter()


def _invalid(errors: list[str]) -> JSONResponse:
    return JSONResponse({"detail": "Tool is invalid: " + "; ".join(errors), "errors": errors}, status_code=422)


def _lint(body: Any) -> tuple[ToolSpec | None, list[str]]:
    if not isinstance(body, dict):
        return None, ["request body must be a JSON object"]
    data = {k: v for k, v in body.items() if k != "args"}
    return lint_tool(data)


@router.get("/api/tools")
async def list_tools(request: Request, agent: str | None = None, q: str | None = None):
    return await deps.services(request).repository().list_tools(agent=agent or None, q=q or None)


@router.post("/api/tools/test")
async def test_tool(request: Request, body: Any = Body(...)):
    spec, errors = _lint(body)
    if spec is None or errors:
        declaration = None
        if spec is not None:
            try:
                declaration = declaration_json(spec)
            except Exception:  # noqa: BLE001
                declaration = None
        return {"ok": False, "errors": errors, "declaration": declaration, "result": None}

    try:
        declaration = declaration_json(spec)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "errors": [f"Could not build the function declaration: {exc}"], "declaration": None,
                "result": None}

    if spec.tool_type == "factual":
        return {"ok": True, "errors": [], "declaration": declaration,
                "result": {"answer": spec.answer, "source": spec.source}}

    supplied = body.get("args") if isinstance(body.get("args"), dict) else {}
    test_args: dict[str, Any] = {}
    missing = []
    for p in spec.params:
        value = supplied.get(p.name)
        if value is None or value == "":
            value = p.example if p.example is not None else p.default
        if value is None and p.required:
            missing.append(p.name)
        test_args[p.name] = value
    if missing:
        return {"ok": False, "declaration": declaration, "result": None,
                "errors": [f"Provide a test value (example) for required parameter '{n}'" for n in missing]}
    try:
        values = validate_args(spec.params, test_args)
    except ToolArgError as exc:
        return {"ok": False, "errors": exc.problems, "declaration": declaration, "result": None}

    executor = deps.services(request).test_executor()
    try:
        result = await executor.run_query(spec, values)
    except ToolExecutionError as exc:
        return {"ok": False, "errors": [str(exc)], "declaration": declaration, "result": None}
    return {
        "ok": True,
        "errors": [],
        "declaration": declaration,
        "result": {"columns": result.columns, "rows": result.rows, "row_count": result.row_count,
                   "truncated": result.truncated, "duration_ms": result.duration_ms},
    }


@router.get("/api/tools/{name}")
async def get_tool(name: str, request: Request):
    tool = await deps.services(request).repository().get_tool(name)
    if tool is None:
        raise HTTPException(404, f"tool '{name}' not found")
    return tool


@router.post("/api/tools", status_code=201)
async def create_tool(request: Request, body: Any = Body(...)):
    spec, errors = _lint(body)
    if spec is None or errors:
        return _invalid(errors)
    try:
        return await deps.services(request).repository().create(spec)
    except ToolExistsError:
        raise HTTPException(409, f"a tool named '{spec.name}' already exists") from None


@router.put("/api/tools/{name}")
async def update_tool(name: str, request: Request, body: Any = Body(...)):
    if not isinstance(body, dict):
        return _invalid(["request body must be a JSON object"])
    if body.get("name") not in (None, name):
        return _invalid(["name is immutable; create a new tool instead of renaming"])
    spec, errors = _lint({**body, "name": name})
    if spec is None or errors:
        return _invalid(errors)
    try:
        return await deps.services(request).repository().update(name, spec)
    except ToolNotFoundError:
        raise HTTPException(404, f"tool '{name}' not found") from None


@router.patch("/api/tools/{name}/enabled")
async def set_enabled(name: str, request: Request, body: Any = Body(...)):
    if not isinstance(body, dict) or not isinstance(body.get("enabled"), bool):
        return _invalid(["body must be {\"enabled\": true|false}"])
    try:
        return await deps.services(request).repository().set_enabled(name, body["enabled"])
    except ToolNotFoundError:
        raise HTTPException(404, f"tool '{name}' not found") from None


@router.delete("/api/tools/{name}")
async def delete_tool(name: str, request: Request):
    try:
        await deps.services(request).repository().delete(name)
    except ToolNotFoundError:
        raise HTTPException(404, f"tool '{name}' not found") from None
    return {"ok": True}
