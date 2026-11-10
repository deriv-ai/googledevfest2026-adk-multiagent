"""finance_agent: answers general-ledger questions with registry tools over the finance schema."""

from __future__ import annotations

from typing import Any

from google.adk.agents import LlmAgent

from .specialists import build_registry_specialist

NAME = "finance_agent"
DESCRIPTION = (
    "Finance specialist for Nimbus Markets. Answers questions about the general ledger: revenue and its "
    "breakdown (trading commission revenue, spread revenue, subscription fees, interest), expenses, "
    "operating profit and margin per month or entity, budget vs actual, legal entities and FX rates. "
    "Pass one self-contained question with explicit dates."
)


def build_finance_agent(services: Any, model: Any) -> LlmAgent:
    return build_registry_specialist(name=NAME, schema="finance", description=DESCRIPTION,
                                     services=services, model=model)
