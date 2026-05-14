"""Centralised configuration loaded from environment / .env file."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from defaults.models import (
    PROVIDER_ANTHROPIC,
    PROVIDER_DEEPSEEK,
    PROVIDER_OPENAI,
    PROVIDER_OPENROUTER,
    ModelConfig,
)

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

_DEFAULT_WEB_PORT = 8070
_WEB_PORT_MIN = 1
_WEB_PORT_MAX = 65535
_DEFAULT_BETA_DAILY_TURNS = 20
_DEFAULT_BETA_WEEKLY_TURNS = 50

_SAFETY_HIGH = "HIGH"
_SAFETY_MEDIUM = "MEDIUM"
_SAFETY_LOW = "LOW"

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
    deepseek_api_key: str | None = None

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

    # Web UI server
    web_port: int = Field(default=_DEFAULT_WEB_PORT, ge=_WEB_PORT_MIN, le=_WEB_PORT_MAX)

    # Supabase Auth / beta gate. Defaults preserve local anonymous-cookie mode.
    supabase_url: str | None = None
    supabase_publishable_key: str | None = None
    supabase_anon_key: str | None = None
    supabase_key: str | None = None
    supabase_jwks_url: str | None = None
    supabase_jwt_audience: str = "authenticated"
    supabase_jwt_issuer: str | None = None
    beta_auth_required: bool = False
    beta_invite_gate_enabled: bool = True

    # Friends beta operating controls. These checks run before web gameplay
    # invokes LLM-backed engine work.
    beta_enabled: bool = True
    beta_kill_message: str = "Storyteller beta is paused while we tune the experience. Please try again later."
    beta_daily_turn_quota: int = Field(default=_DEFAULT_BETA_DAILY_TURNS, ge=0)
    beta_weekly_turn_quota: int = Field(default=_DEFAULT_BETA_WEEKLY_TURNS, ge=0)
    beta_max_active_games: int = Field(default=3, ge=0)
    beta_global_budget_usd: str = "50"
    model_pricing_json: str | None = None

    # Content safety — when enabled (default) the engine runs every player
    # action through inbound moderation and every narrator response through
    # outbound moderation. The OpenAI moderation API is consulted when an
    # ``openai_api_key`` is configured; a prompt-injection heuristic is
    # always on. Per-category thresholds accept severity names
    # (``NONE`` / ``LOW`` / ``MEDIUM`` / ``HIGH``); unknown values log a
    # warning and fall back to safe defaults — see
    # ``safety.thresholds.ModerationThresholds``.
    safety_enabled: bool = True
    safety_threshold_violence: str = _SAFETY_HIGH
    safety_threshold_sexual: str = _SAFETY_HIGH
    safety_threshold_sexual_minors: str = _SAFETY_LOW
    safety_threshold_harassment: str = _SAFETY_HIGH
    safety_threshold_hate: str = _SAFETY_MEDIUM
    safety_threshold_self_harm: str = _SAFETY_MEDIUM
    safety_threshold_illicit: str = _SAFETY_HIGH
    safety_threshold_prompt_injection: str = _SAFETY_MEDIUM

    @property
    def public_supabase_key(self) -> str | None:
        """Return the browser-safe Supabase key, preferring modern naming."""
        return self.supabase_publishable_key or self.supabase_anon_key or self.supabase_key


def load_config() -> Config:
    """Load configuration from a ``.env`` file and/or environment variables.

    Precedence: explicit env vars > ``.env`` file > defaults.
    """
    return Config()


def _detect_provider(model_id: str) -> str:
    """Guess the provider from the model name."""
    model_lower = model_id.lower()
    if any(model_lower.startswith(prefix) for prefix in _OPENROUTER_PREFIXES):
        return PROVIDER_OPENROUTER
    if model_lower.startswith("deepseek-"):
        return PROVIDER_DEEPSEEK
    if model_lower.startswith(("gpt-", "o1", "o3", "o4")):
        return PROVIDER_OPENAI
    if model_lower.startswith(("claude", "claude-")):
        return PROVIDER_ANTHROPIC
    return PROVIDER_OPENAI


def resolve_model_config(model_id: str) -> ModelConfig:
    """Build a ``ModelConfig`` from a model name string.

    Provider is auto-detected from the model name (``gpt-*`` → openai,
    ``claude-*`` → anthropic), defaulting to openai for unknown prefixes.
    Temperature and max_tokens use ``ModelConfig`` defaults.
    """
    return ModelConfig(provider=_detect_provider(model_id), model_id=model_id)


def get_api_key_for_provider(provider: str, config: Config) -> str | None:
    """Return the API key for the given provider, or None."""
    if provider == PROVIDER_OPENAI:
        return config.openai_api_key
    if provider == PROVIDER_ANTHROPIC:
        return config.anthropic_api_key
    if provider == PROVIDER_OPENROUTER:
        return config.openrouter_api_key
    if provider == PROVIDER_DEEPSEEK:
        return config.deepseek_api_key
    return None


def list_api_key_status(config: Config) -> dict[str, bool]:
    """Return ``{provider: bool}`` indicating which providers have a key set."""
    return {
        PROVIDER_OPENAI: bool(config.openai_api_key),
        PROVIDER_ANTHROPIC: bool(config.anthropic_api_key),
        PROVIDER_OPENROUTER: bool(config.openrouter_api_key),
        PROVIDER_DEEPSEEK: bool(config.deepseek_api_key),
    }
