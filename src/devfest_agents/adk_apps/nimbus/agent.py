"""Entry point for ADK's dev UI: `adk web src/devfest_agents/adk_apps` lists this app as `nimbus`."""

from devfest_agents.agents import build_root_agent

root_agent = build_root_agent()
