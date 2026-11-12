from __future__ import annotations

import logging

from fastapi import APIRouter, Request

from ..agents import graph_agents
from ..agents.common import list_tools, tool_title, walk_agents
from ..tracing import tool_kind
from . import deps

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/api/graph")
async def graph(request: Request):
    settings = deps.services(request).settings
    agents = []
    for a in graph_agents():
        item = {k: v for k, v in a.items() if k != "model_role" and v is not None}
        item["model"] = settings.effective_router_model if a["model_role"] == "router" else settings.effective_agent_model
        agents.append(item)

    specialists = [a for a in agents if a["role"] == "specialist"]
    built = {agent.name: agent for agent in walk_agents(deps.runtime(request).root_agent)}
    tools = []
    for a in specialists:
        try:
            agent_tools = await list_tools(built[a["id"]])
        except Exception as exc:  # noqa: BLE001 - e.g. the database is down
            logger.warning("Could not list tools of %s: %s", a["id"], type(exc).__name__)
            agent_tools = []
        tools.extend({"name": t.name, "agent": a["id"], "tool_type": tool_kind(t), "title": tool_title(t)}
                     for t in agent_tools)

    datasources = [{"id": a["datasource"], "label": f"{a['datasource']} schema"} for a in specialists]
    return {"agents": agents, "tools": tools, "datasources": datasources}
