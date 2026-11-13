"""Workshop participants edit only my_agent/; these pin down what lives there."""

from devfest_agents import agents
from devfest_agents.agents.common import prompt_path
from devfest_agents.config import REPO_ROOT


def test_participant_prompts_come_from_my_agent():
    for name in ("marketing_agent", "orchestrator", "main_agent"):
        assert prompt_path(name).parent == REPO_ROOT / "my_agent" / "prompts"


def test_platform_prompts_stay_in_the_platform():
    assert prompt_path("finance_agent").parent.name == "prompts"
    assert "platform" in prompt_path("finance_agent").parts


def test_the_team_list_comes_from_my_agent(monkeypatch):
    from my_agent import team

    monkeypatch.undo()  # conftest swaps in a test team
    assert agents.SPECIALISTS is team.SPECIALISTS


def test_the_starting_orchestrator_names_the_campaign_gap():
    from devfest_agents.check import GAP_HEADING

    assert GAP_HEADING in prompt_path("orchestrator").read_text()
