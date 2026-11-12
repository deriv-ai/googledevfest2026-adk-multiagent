"""The team: the specialist agents the orchestrator can call.

Every agent in SPECIALISTS becomes a tool for the orchestrator. Exercise 3: add yours.
"""

from devfest_agents.agents import finance_agent, news_agent, trading_agent

SPECIALISTS = [finance_agent, trading_agent, news_agent]
