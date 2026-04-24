"""Centralised configuration loaded from environment / .env file."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from defaults.models import PROVIDER_ANTHROPIC, PROVIDER_OPENAI, PROVIDER_OPENROUTER, ModelConfig

_GPT5_4_MINI = "gpt-5.4-mini"
_GPT5_4_NANO = "gpt-5.4-nano"

_OPENROUTER_PREFIXES = (
    "deepseek/",
    "google/",
    "x-ai/",
    "qwen/",
    "moonshotai/",
    "meta-llama/",
    "mistralai/",
)

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
    openrouter_api_key: str | None = None

    # Model selection per agent role
    director_model: str = _GPT5_4_MINI
    agent_model: str = _GPT5_4_NANO
    narrator_model: str = _GPT5_4_MINI
    dramaturge_model: str = _GPT5_4_NANO

    # Dramaturge (consistency oracle) is off by default — enable via env
    # var ``DRAMATURGE_ENABLED=true``. When enabled, a validation pass runs
    # after the Narrator on new-scene turns and rewrites sentences that
    # contradict historical canon or prior in-scene dialogue.
    dramaturge_enabled: bool = False

    # Telegram
    telegram_bot_token: str | None = None

    # Defaults
    default_provider: str = PROVIDER_OPENAI
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
    if any(model_lower.startswith(prefix) for prefix in _OPENROUTER_PREFIXES):
        return PROVIDER_OPENROUTER
    if model_lower.startswith(("gpt-", "o1", "o3", "o4")):
        return PROVIDER_OPENAI
    if model_lower.startswith(("claude", "claude-")):
        return PROVIDER_ANTHROPIC
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
    if provider == PROVIDER_OPENAI:
        return config.openai_api_key
    if provider == PROVIDER_ANTHROPIC:
        return config.anthropic_api_key
    if provider == PROVIDER_OPENROUTER:
        return config.openrouter_api_key
    return None


def list_api_key_status(config: Config) -> dict[str, bool]:
    """Return ``{provider: bool}`` indicating which providers have a key set."""
    return {
        PROVIDER_OPENAI: bool(config.openai_api_key),
        PROVIDER_ANTHROPIC: bool(config.anthropic_api_key),
        PROVIDER_OPENROUTER: bool(config.openrouter_api_key),
    }
