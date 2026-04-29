"""Helpers for admin_routes_settings — kept separate to respect module-member limits."""

from __future__ import annotations

from types import MappingProxyType
from typing import Mapping

from config import Config, resolve_model_config
from db import repo_settings
from defaults.models import AI_MODELS, ModelConfig
from interfaces.admin_routes_settings_validation import FIELD_MODEL_ID, FIELD_PROVIDER

_ROLE_TO_ENV_FIELD: Mapping[str, str] = MappingProxyType(
    {
        "director": "director_model",
        "agent": "agent_model",
        "narrator": "narrator_model",
        "dramaturge": "dramaturge_model",
    },
)

_SOURCE_ENV = "env"
_SOURCE_DB = "db"

_KEY_SOURCE = "source"

_CATALOG_ATTRIBUTES: tuple[str, ...] = (
    "gpt5_4",
    "gpt5_4_mini",
    "gpt5_4_nano",
    "claude_opus",
    "claude_sonnet",
    "claude_haiku",
    "deepseek_chat",
    "deepseek_v4_pro",
    "gemini_pro",
    "gemini_flash",
    "grok_fast",
    "deepseek_native_chat",
    "deepseek_native_reasoner",
)


def build_catalog() -> list[dict[str, str]]:
    """Serialize :data:`AI_MODELS` into a UI-friendly catalog list (stable order)."""
    catalog: list[dict[str, str]] = []
    for attr in _CATALOG_ATTRIBUTES:
        entry = getattr(AI_MODELS, attr, None)
        if isinstance(entry, ModelConfig):
            catalog.append({FIELD_PROVIDER: entry.provider, FIELD_MODEL_ID: entry.model_id})
    return catalog


def _entry_from_override(stored: tuple[str, str]) -> dict[str, str]:
    provider, model_id = stored
    return {FIELD_PROVIDER: provider, FIELD_MODEL_ID: model_id, _KEY_SOURCE: _SOURCE_DB}


def _entry_from_env(role: str, cfg: Config) -> dict[str, str]:
    env_model = resolve_model_config(getattr(cfg, _ROLE_TO_ENV_FIELD[role]))
    return {
        FIELD_PROVIDER: env_model.provider,
        FIELD_MODEL_ID: env_model.model_id,
        _KEY_SOURCE: _SOURCE_ENV,
    }


def merge_role_entries(
    db_overrides: dict[str, tuple[str, str]],
    cfg: Config,
) -> dict[str, dict[str, str]]:
    """Blend DB overrides on top of env defaults for every known role."""
    roles: dict[str, dict[str, str]] = {}
    for role in repo_settings.ALLOWED_ROLES:
        stored = db_overrides.get(role)
        roles[role] = _entry_from_override(stored) if stored else _entry_from_env(role, cfg)
    return roles
