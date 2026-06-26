"""Environment-driven settings (pydantic-settings). Secrets come from env only."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Anthropic / LLM stage -------------------------------------------------
    anthropic_api_key: str | None = None            # ANTHROPIC_API_KEY (env only)
    llm_model: str = "claude-sonnet-4-6"            # explicitly chosen in the brief
    llm_max_tokens: int = 1024
    llm_timeout: float = 30.0                        # seconds, per LLM call
    max_retries: int = 3                             # SDK exponential backoff

    # --- Fast local classifier -------------------------------------------------
    classifier_model: str = "ProsusAI/finbert"       # swap to a social model freely
    classifier_max_length: int = 256

    # --- Confidence gate -------------------------------------------------------
    conf_threshold: float = 0.85                     # escalate below this confidence
    margin_threshold: float = 0.15                   # escalate if top-2 margin below
    escalate_on_length: int = 0                      # >0 enables long-text escalation

    # --- Judge / concurrency ---------------------------------------------------
    enable_judge: bool = False
    max_llm_concurrency: int = 5                     # bounded in-flight Anthropic calls

    # --- Optional self-hosted LLM fallback (OpenAI-compatible endpoint) ---------
    local_llm_base_url: str | None = None            # e.g. http://localhost:11434/v1
    local_llm_model: str = "qwen2.5:7b-instruct"

    @property
    def claude_enabled(self) -> bool:
        return bool(self.anthropic_api_key)


_settings: Settings | None = None


def get_settings() -> Settings:
    """Cached singleton so env is read once."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
