from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from ..schema_introspect import MAX_SAMPLE, SCHEMAS, UnknownSchemaObject
from . import deps

router = APIRouter()


@router.get("/api/schema")
async def list_schemas(request: Request):
    return await deps.schema_service(request).list_schemas()


@router.get("/api/schema/{schema}")
async def describe_schema(schema: str, request: Request):
    if schema not in SCHEMAS:
        raise HTTPException(404, f"unknown schema '{schema}' (expected one of {', '.join(SCHEMAS)})")
    try:
        return await deps.schema_service(request).describe(schema)
    except UnknownSchemaObject:
        raise HTTPException(404, f"schema '{schema}' not found in the database") from None


@router.get("/api/schema/{schema}/{table}/sample")
async def sample(schema: str, table: str, request: Request, limit: int = Query(5, ge=1, le=MAX_SAMPLE)):
    if schema not in SCHEMAS:
        raise HTTPException(404, f"unknown schema '{schema}'")
    try:
        return await deps.schema_service(request).sample(schema, table, limit)
    except UnknownSchemaObject:
        raise HTTPException(404, f"unknown table '{schema}.{table}'") from None
