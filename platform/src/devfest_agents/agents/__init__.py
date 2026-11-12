"""Agent tree:

    main_agent ──AgentTool──> orchestrator ──AgentTool──> finance_agent  (SqlRegistryToolset: finance)
                                           └─AgentTool──> trading_agent  (SqlRegistryToolset: trading)

Every specialist module has NAME, LABEL, DATASOURCE, DESCRIPTION and build(services, model).
The team list, SPECIALISTS, lives in my_agent/team.py so workshop participants can add to it.
"""

from __future__ import annotations

from typing import Any

from google.adk.agents import LlmAgent

from .. import tracing
from ..services import Services, get_services
from . import main_agent, orchestrator
from .common import ModelFactory

# Imported last: team.py imports finance_agent and trading_agent from this package.
from my_agent.team import SPECIALISTS  # noqa: E402


def graph_agents() -> list[dict[str, Any]]:
    """Topology for GET /api/graph (labels/roles/datasources)."""
    return [
        {"id": main_agent.NAME, "label": "Main agent", "role": "root", "parent": None,
         "description": main_agent.DESCRIPTION, "model_role": "router"},
        {"id": orchestrator.NAME, "label": "Orchestrator", "role": "router", "parent": main_agent.NAME,
         "description": orchestrator.DESCRIPTION, "model_role": "router"},
        *({"id": m.NAME, "label": m.LABEL, "role": "specialist", "parent": orchestrator.NAME,
           "description": m.DESCRIPTION, "datasource": m.DATASOURCE, "model_role": "agent"} for m in SPECIALISTS),
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
    specialists = [module.build(services, models("agent")) for module in SPECIALISTS]
    for agent in specialists:
        tracing.attach(agent)
    orch = orchestrator.build_orchestrator(models("router"), specialists, guard)
    return main_agent.build_main_agent(models("router"), orch, guard)


__all__ = ["build_root_agent", "graph_agents", "SPECIALISTS"]
