"""Settings read from the environment (and `.env` for local runs).

The Gemini key is held as a SecretStr so it never ends up in logs or repr().
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# platform/src/devfest_agents/config.py. The container mirrors this layout under /app.
PLATFORM_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = PLATFORM_ROOT.parent  # also holds my_agent/ and evals/


PLACEHOLDER_KEY = "later"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # LLM: LITELLM_GEMINI_API_KEY (or LLM_API_KEY) takes precedence over GEMINI_API_KEY.
    # When OPENAI_BASE_URL (or LLM_BASE_URL) is set we talk to an OpenAI-compatible
    # LiteLLM proxy ("proxy" mode); otherwise straight to Gemini ("direct" mode).
    litellm_gemini_api_key: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("litellm_gemini_api_key", "llm_api_key"))
    gemini_api_key: SecretStr | None = None
    openai_base_url: SecretStr | None = Field(
        default=None, validation_alias=AliasChoices("openai_base_url", "llm_base_url"))
    agent_model: str | None = None
    router_model: str | None = None
    # Optional: "low" | "medium" | "high" passed to LiteLLM as reasoning_effort
    # (lower = faster answers on reasoning models). Defaults to "low": measured
    # 125 s -> ~27 s for a cross-agent turn on gemini-3.8-flash. Set it to an empty
    # value to fall back to the provider default.
    llm_reasoning_effort: str | None = "low"
    # Per-LLM-call timeout and retries. LiteLLM's default (600 s + retries) turned a
    # proxy hiccup into a 4-minute hang; fail fast and retry a couple of times instead.
    llm_timeout_seconds: float = Field(default=60.0, gt=0, le=600)
    llm_num_retries: int = Field(default=2, ge=0, le=5)

    database_url: str = "postgresql://app:app@db:5432/nimbus"
    agent_database_url: str = "postgresql://agent_ro:agent_ro@db:5432/nimbus"
    news_mcp_url: str = "http://news-mcp:8001/mcp"

    static_dir: str = "/app/static"
    starter_tools_path: str = "/app/seed/starter_tools.yaml"

    tool_max_rows: int = Field(default=200, ge=1, le=5000)
    max_delegations: int = Field(default=4, ge=1, le=20)
    max_tool_calls: int = Field(default=8, ge=1, le=50)  # per specialist, per request
    log_level: str = "INFO"

    @field_validator("router_model", "agent_model", "llm_reasoning_effort", "gemini_api_key", "litellm_gemini_api_key",
                     "openai_base_url", mode="before")
    @classmethod
    def _blank_is_none(cls, value):
        if isinstance(value, str) and not value.strip():
            return None
        return value

    # ----- computed helpers -------------------------------------------------
    @property
    def llm_mode(self) -> str:
        return "proxy" if self.openai_base_url is not None else "direct"

    @property
    def llm_api_key(self) -> str | None:
        for secret in (self.litellm_gemini_api_key, self.gemini_api_key):
            if secret is not None and secret.get_secret_value().strip():
                return secret.get_secret_value().strip()
        return None

    @property
    def llm_api_base(self) -> str | None:
        return self.openai_base_url.get_secret_value().strip() if self.openai_base_url is not None else None

    @property
    def effective_agent_model(self) -> str:
        if self.agent_model:
            return self.agent_model
        return "openai/gemini-3.7-flash" if self.llm_mode == "proxy" else "gemini/gemini-3.7-flash"

    @property
    def effective_router_model(self) -> str:
        return self.router_model or self.effective_agent_model

    @property
    def llm_key_configured(self) -> bool:
        # "later" is the README's stand-in for building before the session: not a key.
        key = self.llm_api_key
        return key is not None and key.lower() != PLACEHOLDER_KEY

    def secret_values(self) -> list[str]:
        """Values that must be scrubbed from any error text sent to a client."""
        out = [s.get_secret_value() for s in (self.litellm_gemini_api_key, self.gemini_api_key, self.openai_base_url)
               if s is not None]
        return [v.strip() for v in out if len(v.strip()) >= 6]

    def scrub(self, text: str) -> str:
        for secret in self.secret_values():
            text = text.replace(secret, "***")
        return text

    @property
    def resolved_static_dir(self) -> Path | None:
        return _first_existing(Path(self.static_dir), PLATFORM_ROOT / "web" / "dist")

    @property
    def resolved_starter_tools_path(self) -> Path | None:
        return _first_existing(Path(self.starter_tools_path), PLATFORM_ROOT / "seed" / "starter_tools.yaml")


def _first_existing(*candidates: Path) -> Path | None:
    for path in candidates:
        if path.exists():
            return path
    return None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
