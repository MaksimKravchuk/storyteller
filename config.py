"""Centralised configuration loaded from environment / .env file."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict

from defaults.models import ModelConfig

_GPT4 = "gpt-4"
_GPT35_TURBO = "gpt-3.5-turbo"
_PROVIDER_OPENAI = "openai"


class Config(BaseSettings):
    """All runtime configuration for the Storyteller engine."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # API keys (None means the SDK will try its own env-var fallback)
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None

    # Model selection per agent role
    director_model: str = _GPT4
    agent_model: str = _GPT35_TURBO
    narrator_model: str = _GPT4

    # Telegram
    telegram_bot_token: str | None = None

    # Defaults
    default_provider: str = _PROVIDER_OPENAI
    temperature: float = 0.7
    max_tokens: int = 2048


def load_config(env_path: str | None = None) -> Config:
    """Load configuration from a ``.env`` file and/or environment variables.

    Precedence: explicit env vars > ``.env`` file > defaults.
    """
    if env_path is not None:
        return Config(_env_file=env_path)  # type: ignore[call-arg]
    return Config()


def _detect_provider(model_id: str, fallback: str) -> str:
    """Guess the provider from the model name."""
    model_lower = model_id.lower()
    if model_lower.startswith(("gpt-", "o1", "o3", "o4")):
        return _PROVIDER_OPENAI
    if model_lower.startswith(("claude", "claude-")):
        return "anthropic"
    return fallback


def resolve_model_config(model_id: str, config: Config) -> ModelConfig:
    """Build a ``ModelConfig`` from a model name string + global config.

    Provider is auto-detected from the model name (``gpt-*`` → openai,
    ``claude-*`` → anthropic), falling back to ``config.default_provider``.
    """
    provider = _detect_provider(model_id, config.default_provider)
    return ModelConfig(
        provider=provider,
        model_id=model_id,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
    )


def get_api_key_for_provider(provider: str, config: Config) -> str | None:
    """Return the API key for the given provider, or None."""
    if provider == _PROVIDER_OPENAI:
        return config.openai_api_key
    if provider == "anthropic":
        return config.anthropic_api_key
    return None
