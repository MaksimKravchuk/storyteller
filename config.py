"""Centralised configuration loaded from environment / .env file."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from defaults.models import ModelConfig

_GPT5_4_MINI = "gpt-5.4-mini"
_GPT5_4_NANO = "gpt-5.4-nano"
_CLAUDE_SONNET_REVIEWER = "claude-sonnet-4-20250514"
_PROVIDER_OPENAI = "openai"

_DEFAULT_TEMPERATURE = 0.7
_TEMPERATURE_MIN = float(0)
_TEMPERATURE_MAX = 2.0
_DEFAULT_MAX_TOKENS = 2048

_DEFAULT_WEB_HOST = "127.0.0.1"
_DEFAULT_WEB_PORT = 8070
_WEB_PORT_MIN = 1
_WEB_PORT_MAX = 65535

# Anchor the default ``.env`` to the project root (this file's directory)
# rather than CWD, so that ``load_config()`` works regardless of where the
# process was launched from. python-dotenv's ``find_dotenv()`` used to
# achieve this via frame-walking; pydantic-settings does not, so we resolve
# the path explicitly.
_DEFAULT_ENV_FILE = Path(__file__).parent / ".env"


class Config(BaseSettings):
    """All runtime configuration for the Storyteller engine."""

    model_config = SettingsConfigDict(
        env_file=_DEFAULT_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # API keys (None means the SDK will try its own env-var fallback)
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None

    # Model selection per agent role
    director_model: str = _GPT5_4_MINI
    agent_model: str = _GPT5_4_NANO
    narrator_model: str = _GPT5_4_MINI
    # Narrative Test Agent runs out-of-band and audits the game's narrative
    # across six dimensions (story, turns, scenes, confrontation, memory,
    # autonomy). It needs a higher-tier model than the per-turn agents,
    # so the default points at Claude Sonnet rather than gpt-5.4-mini.
    narrative_test_model: str = _CLAUDE_SONNET_REVIEWER

    # Telegram
    telegram_bot_token: str | None = None

    # Defaults
    default_provider: str = _PROVIDER_OPENAI
    temperature: float = Field(default=_DEFAULT_TEMPERATURE, ge=_TEMPERATURE_MIN, le=_TEMPERATURE_MAX)
    max_tokens: int = Field(default=_DEFAULT_MAX_TOKENS, gt=0)

    # Web UI server
    web_host: str = _DEFAULT_WEB_HOST
    web_port: int = Field(default=_DEFAULT_WEB_PORT, ge=_WEB_PORT_MIN, le=_WEB_PORT_MAX)


def load_config(env_path: str | None = None) -> Config:
    """Load configuration from a ``.env`` file and/or environment variables.

    Precedence: explicit env vars > ``.env`` file > defaults.

    Raises:
        FileNotFoundError: if ``env_path`` is provided but does not exist.
    """
    if env_path is not None:
        if not Path(env_path).is_file():
            raise FileNotFoundError(
                "Config env file not found: {0}. Pass an existing path or omit env_path.".format(env_path),
            )
        # ``_env_file`` is injected at runtime by pydantic-settings; mypy can't see it.
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
