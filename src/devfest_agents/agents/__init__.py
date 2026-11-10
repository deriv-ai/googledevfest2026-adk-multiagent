"""Agent tree:

    main_agent ──AgentTool──> orchestrator ──AgentTool──> finance_agent  (SqlRegistryToolset: finance)
                                           ├─AgentTool──> trading_agent  (SqlRegistryToolset: trading)
                                           └─AgentTool──> news_agent     (McpToolset: news-mcp)
"""

from __future__ import annotations

from typing import Any

from google.adk.agents import LlmAgent

from .. import tracing
from ..services import Services, get_services
from . import finance_agent, main_agent, news_agent, orchestrator, trading_agent
from .common import ModelFactory

# Static topology for GET /api/graph (labels/roles/datasources).
GRAPH_AGENTS = [
    {"id": main_agent.NAME, "label": "Main agent", "role": "root", "parent": None,
     "description": main_agent.DESCRIPTION, "model_role": "router"},
    {"id": orchestrator.NAME, "label": "Orchestrator", "role": "router", "parent": main_agent.NAME,
     "description": orchestrator.DESCRIPTION, "model_role": "router"},
    {"id": finance_agent.NAME, "label": "Finance agent", "role": "specialist", "parent": orchestrator.NAME,
     "description": finance_agent.DESCRIPTION, "datasource": "finance", "model_role": "agent"},
    {"id": trading_agent.NAME, "label": "Trading agent", "role": "specialist", "parent": orchestrator.NAME,
     "description": trading_agent.DESCRIPTION, "datasource": "trading", "model_role": "agent"},
    {"id": news_agent.NAME, "label": "News agent", "role": "specialist", "parent": orchestrator.NAME,
     "description": news_agent.DESCRIPTION, "datasource": "internet", "model_role": "agent"},
]


def default_model_factory(services: Services) -> ModelFactory:
    from .model import agent_model, router_model

    def factory(role: str) -> Any:
        return router_model(services.settings) if role == "router" else agent_model(services.settings)

    return factory


def build_root_agent(services: Services | None = None, *, model_factory: ModelFactory | None = None) -> LlmAgent:
    """Build the whole tree. Touches no network: toolsets connect lazily."""
    services = services or get_services()
    models = model_factory or default_model_factory(services)
    guard = tracing.DelegationGuard(services.settings.max_delegations)
    specialists = [
        finance_agent.build_finance_agent(services, models("agent")),
        trading_agent.build_trading_agent(services, models("agent")),
        news_agent.build_news_agent(services, models("agent")),
    ]
    orch = orchestrator.build_orchestrator(services, models("router"), specialists, guard)
    return main_agent.build_main_agent(models("router"), orch, guard)


__all__ = ["build_root_agent", "GRAPH_AGENTS"]
