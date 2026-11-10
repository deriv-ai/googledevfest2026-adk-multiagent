from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Request

from ..agents import GRAPH_AGENTS
from ..tools.news_toolset import NEWS_TOOLS
from . import deps

router = APIRouter()
logger = logging.getLogger(__name__)

DATASOURCES = [
    {"id": "finance", "label": "finance schema"},
    {"id": "trading", "label": "trading schema"},
    {"id": "internet", "label": "Internet (RSS)"},
]


@router.get("/api/graph")
async def graph(request: Request):
    svc = deps.services(request)
    settings = svc.settings
    agents = []
    for a in GRAPH_AGENTS:
        item = {k: v for k, v in a.items() if k != "model_role" and v is not None}
        item["model"] = settings.effective_router_model if a["model_role"] == "router" else settings.effective_agent_model
        agents.append(item)

    tools = []
    for agent_id, schema in (("finance_agent", "finance"), ("trading_agent", "trading")):
        try:
            specs, _ = await svc.cache(schema).refresh()
        except Exception:  # noqa: BLE001
            specs = []
        tools.extend({"name": s.name, "agent": agent_id, "tool_type": s.tool_type, "title": s.title} for s in specs)

    news = svc.news()
    names = list(getattr(news, "last_tool_names", None) or [])
    if not names:
        try:
            listed = await asyncio.wait_for(news.get_tools(), timeout=4.0)
            names = [t.name for t in listed]
        except Exception:  # noqa: BLE001
            names = []
    for name in names or list(NEWS_TOOLS):
        tools.append({"name": name, "agent": "news_agent", "tool_type": "mcp", "title": NEWS_TOOLS.get(name, name)})

    return {"agents": agents, "tools": tools, "datasources": DATASOURCES}
