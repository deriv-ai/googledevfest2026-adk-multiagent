import pytest

from devfest_agents import agents
from devfest_agents.services import set_services

from .helpers import PYTHON_SPECIALIST, make_fake_services, make_settings


@pytest.fixture(autouse=True)
def specialists(monkeypatch):
    """Finance, trading, news and a Python-tool specialist, whatever the workshop state of SPECIALISTS."""
    monkeypatch.setattr(agents, "SPECIALISTS", [agents.finance_agent, agents.trading_agent, agents.news_agent,
                                                PYTHON_SPECIALIST])


@pytest.fixture
def settings():
    return make_settings()


@pytest.fixture
def fake_services(settings):
    """Also installed as the global services: hand-written tools (run_sql) use get_services()."""
    services = make_fake_services(settings)
    set_services(services)
    yield services
    set_services(None)
