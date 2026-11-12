from __future__ import annotations

from fastapi import APIRouter, Request

from . import deps

router = APIRouter()


@router.get("/api/health")
async def health(request: Request):
    svc = deps.services(request)
    settings = svc.settings
    db_ok = await svc.database().ping()
    return {
        "ok": True,
        "db": "ok" if db_ok else "error",
        "llm_key": "configured" if settings.llm_key_configured else "missing",
        "llm_mode": settings.llm_mode,
        "model": settings.effective_agent_model,
        "router_model": settings.effective_router_model,
    }
