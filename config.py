"""Centralised configuration loaded from environment / .env file."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

from defaults import ModelConfig


@dataclass
class Config:
    """All runtime configuration for the Storyteller engine."""

    # API keys (None means the SDK will try its own env-var fallback)
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None

    # Model selection per agent role
    director_model: str = "gpt-4"
    agent_model: str = "gpt-3.5-turbo"
    narrator_model: str = "gpt-4"

    # Telegram
    telegram_bot_token: str | None = None

    # Defaults
    default_provider: str = "openai"
    temperature: float = 0.7
    max_tokens: int = 2048


def load_config(env_path: str | None = None) -> Config:
    """Load configuration from a ``.env`` file and/or environment variables.

    Precedence: explicit env vars > ``.env`` file > defaults.
    """
    load_dotenv(dotenv_path=env_path, override=False)

    return Config(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
        director_model=os.getenv("DIRECTOR_MODEL", "gpt-4"),
        agent_model=os.getenv("AGENT_MODEL", "gpt-3.5-turbo"),
        narrator_model=os.getenv("NARRATOR_MODEL", "gpt-4"),
        default_provider=os.getenv("DEFAULT_PROVIDER", "openai"),
        temperature=float(os.getenv("TEMPERATURE", "0.7")),
        max_tokens=int(os.getenv("MAX_TOKENS", "2048")),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
    )


def _detect_provider(model_id: str, fallback: str) -> str:
    """Guess the provider from the model name."""
    model_lower = model_id.lower()
    if model_lower.startswith(("gpt-", "o1", "o3", "o4")):
        return "openai"
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
    if provider == "openai":
        return config.openai_api_key
    if provider == "anthropic":
        return config.anthropic_api_key
    return None
