from devfest_agents.agents.model import make_model
from devfest_agents.config import Settings


def test_direct_mode_defaults():
    s = Settings(_env_file=None, gemini_api_key="g" * 12)
    assert s.llm_mode == "direct" and s.effective_agent_model == "gemini/gemini-3.8-flash"
    assert s.effective_router_model == s.effective_agent_model
    m = make_model(s.effective_agent_model, s)
    assert m.model == "gemini/gemini-3.8-flash"
    assert m._additional_args == {"api_key": "g" * 12, "timeout": 60.0, "num_retries": 2, "reasoning_effort": "low", "drop_params": True}  # no max_tokens


def test_proxy_mode_and_key_precedence():
    s = Settings(_env_file=None, gemini_api_key="g" * 12, litellm_gemini_api_key="l" * 12,
                 openai_base_url="https://proxy.invalid/v1", router_model="openai/gemini-3.5-flash")
    assert s.llm_mode == "proxy" and s.llm_api_key == "l" * 12
    assert s.effective_agent_model == "openai/gemini-3.8-flash"
    assert s.effective_router_model == "openai/gemini-3.5-flash"
    m = make_model(s.effective_agent_model, s)
    assert m._additional_args == {"api_key": "l" * 12, "api_base": "https://proxy.invalid/v1", "timeout": 60.0, "num_retries": 2, "reasoning_effort": "low", "drop_params": True}
    assert "max_tokens" not in m._additional_args


def test_secrets_never_in_repr_and_scrubbed():
    s = Settings(_env_file=None, litellm_gemini_api_key="sk-secret-123", openai_base_url="https://corp.invalid/v1")
    assert "sk-secret-123" not in repr(s) and "corp.invalid" not in repr(s)
    assert s.scrub("bad key sk-secret-123 at https://corp.invalid/v1") == "bad key *** at ***"


def test_blank_values_are_unset():
    s = Settings(_env_file=None, gemini_api_key="", openai_base_url="  ", agent_model="")
    assert not s.llm_key_configured and s.llm_mode == "direct" and s.agent_model is None
