import pytest

from devfest_agents.agents.model import make_model
from devfest_agents.config import Settings


def test_direct_mode_defaults():
    s = Settings(_env_file=None, gemini_api_key="g" * 12)
    assert s.llm_mode == "direct" and s.effective_agent_model == "gemini/gemini-3.7-flash"
    assert s.effective_router_model == s.effective_agent_model
    m = make_model(s.effective_agent_model, s)
    assert m.model == "gemini/gemini-3.7-flash"
    assert m._additional_args == {"api_key": "g" * 12, "timeout": 60.0, "num_retries": 2, "reasoning_effort": "low", "drop_params": True}  # no max_tokens


def test_proxy_mode_and_key_precedence():
    s = Settings(_env_file=None, gemini_api_key="g" * 12, litellm_gemini_api_key="l" * 12,
                 openai_base_url="https://proxy.invalid/v1", router_model="openai/gemini-3.5-flash")
    assert s.llm_mode == "proxy" and s.llm_api_key == "l" * 12
    assert s.effective_agent_model == "openai/gemini-3.7-flash"
    assert s.effective_router_model == "openai/gemini-3.5-flash"
    m = make_model(s.effective_agent_model, s)
    assert m._additional_args == {"api_key": "l" * 12, "api_base": "https://proxy.invalid/v1", "timeout": 60.0, "num_retries": 2, "reasoning_effort": "low", "drop_params": True}
    assert "max_tokens" not in m._additional_args


@pytest.mark.parametrize("typed", ["gemini-3.7-flash", "models/gemini-3.7-flash", " gemini-3.7-flash ",
                                   "gemini/gemini-3.7-flash"])
def test_ai_studio_model_name_as_typed(typed):
    s = Settings(_env_file=None, litellm_gemini_api_key="AIza" + "x" * 35, agent_model=typed)
    assert s.effective_agent_model == "gemini/gemini-3.7-flash"
    assert s.effective_router_model == "gemini/gemini-3.7-flash"


def test_ai_studio_key_ignores_a_leftover_proxy_url():
    s = Settings(_env_file=None, litellm_gemini_api_key="AIza" + "x" * 35,
                 openai_base_url="https://proxy.invalid/v1", agent_model="gemini-3.7-flash")
    assert s.llm_mode == "direct" and s.effective_agent_model == "gemini/gemini-3.7-flash"
    assert "api_base" not in make_model(s.effective_agent_model, s)._additional_args


def test_bare_model_name_in_proxy_mode_gets_openai_prefix():
    s = Settings(_env_file=None, litellm_gemini_api_key="sk-proxy-key", openai_base_url="https://proxy.invalid/v1",
                 agent_model="gemini-3.7-flash", router_model="gemini-3.5-flash")
    assert s.effective_agent_model == "openai/gemini-3.7-flash"
    assert s.effective_router_model == "openai/gemini-3.5-flash"


def test_secrets_never_in_repr_and_scrubbed():
    s = Settings(_env_file=None, litellm_gemini_api_key="sk-secret-123", openai_base_url="https://corp.invalid/v1")
    assert "sk-secret-123" not in repr(s) and "corp.invalid" not in repr(s)
    assert s.scrub("bad key sk-secret-123 at https://corp.invalid/v1") == "bad key *** at ***"


def test_blank_values_are_unset():
    s = Settings(_env_file=None, gemini_api_key="", openai_base_url="  ", agent_model="")
    assert not s.llm_key_configured and s.llm_mode == "direct" and s.agent_model is None


@pytest.mark.parametrize("placeholder", ["later", " Later ", "LATER"])
def test_the_pre_session_placeholder_key_is_not_configured(placeholder):
    # README: build before the session with LLM_API_KEY=later, then paste the real key.
    s = Settings(_env_file=None, litellm_gemini_api_key=placeholder)
    assert not s.llm_key_configured
    assert Settings(_env_file=None, litellm_gemini_api_key="sk-real-key").llm_key_configured
