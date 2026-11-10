from __future__ import annotations

import asyncio

import httpx
from fastapi import APIRouter, Request

from . import deps

router = APIRouter()


async def _news_ok(url: str) -> bool:
    """Any HTTP response from the MCP endpoint means the server is up
    (a bare GET on a streamable-HTTP endpoint usually answers 4xx)."""
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            await client.get(url)
        return True
    except Exception:  # noqa: BLE001
        return False


@router.get("/api/health")
async def health(request: Request):
    svc = deps.services(request)
    settings = svc.settings
    db_ok, news_ok = await asyncio.gather(svc.database().ping(), _news_ok(settings.news_mcp_url))
    return {
        "ok": True,
        "db": "ok" if db_ok else "error",
        "news_mcp": "ok" if news_ok else "error",
        "llm_key": "configured" if settings.llm_key_configured else "missing",
        "llm_mode": settings.llm_mode,
        "model": settings.effective_agent_model,
        "router_model": settings.effective_router_model,
    }
