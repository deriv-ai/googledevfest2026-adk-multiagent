"""trading_agent: answers brokerage questions with registry tools over the trading schema."""

from __future__ import annotations

from typing import Any

from google.adk.agents import LlmAgent

from .specialists import build_registry_specialist

NAME = "trading_agent"
LABEL = "Trading agent"
DATASOURCE = "trading"
DESCRIPTION = (
    "Trading specialist for Nimbus Markets. Answers questions about brokerage activity: number of trades, "
    "notional volume, commission earned per instrument / asset class / client segment / country, client PnL "
    "and win rates, active and new clients, instruments and daily prices. "
    "Pass one self-contained question with explicit dates."
)


def build(services: Any, model: Any) -> LlmAgent:
    return build_registry_specialist(name=NAME, schema=DATASOURCE, description=DESCRIPTION,
                                     services=services, model=model)
