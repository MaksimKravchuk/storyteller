"""Admin endpoints for API-key status and per-role model overrides."""

from __future__ import annotations

import inspect
from types import MappingProxyType
from typing import Mapping

from fastapi import Request
from starlette.responses import Response

from config import Config, get_api_key_for_provider, list_api_key_status, resolve_model_config
from db import repo_settings
from defaults.models import AI_MODELS, ModelConfig
from interfaces.admin_json import _json_response
from interfaces import admin_route_helpers as helpers
from interfaces.admin_routes_settings_validation import (
    FIELD_MODEL_ID,
    FIELD_PROVIDER,
    FIELD_ROLE,
    error_response,
    parse_json_body,
    validate_set_model_payload,
)

_HTTP_BAD_REQUEST = 400
_HTTP_CONFLICT = 409

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


def build_catalog() -> list[dict[str, str]]:
    """Serialize :data:`AI_MODELS` into a UI-friendly catalog list.

    Auto-discovers every ``ModelConfig`` declared on :class:`AI_MODELS` so
    new entries appear in the admin UI without a parallel update here.
    Order is alphabetical (``inspect.getmembers``).
    """
    members = inspect.getmembers(AI_MODELS, predicate=lambda member: isinstance(member, ModelConfig))
    return [{FIELD_PROVIDER: entry.provider, FIELD_MODEL_ID: entry.model_id} for _, entry in members]


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


async def get_keys(request: Request) -> Response:
    """Report ``{provider: bool}`` — whether each provider's API key is set."""
    cfg = helpers.get_cfg(request)
    return _json_response(list_api_key_status(cfg))


async def get_models(request: Request) -> Response:
    """Report current effective model per role plus the UI catalog."""
    cfg = helpers.get_cfg(request)
    async with helpers.open_repo(request) as repo:
        db_overrides = await repo.settings.get_model_overrides()
    return _json_response(
        {
            "roles": merge_role_entries(db_overrides, cfg),
            "catalog": build_catalog(),
        }
    )


async def _write_override(
    request: Request,
    role: str,
    provider: str,
    model_id: str,
) -> Response:
    """Persist the override and return the success payload, or a 4xx response."""
    if not get_api_key_for_provider(provider, helpers.get_cfg(request)):
        return error_response("no api key configured for provider {0}".format(provider), _HTTP_CONFLICT)
    async with helpers.open_repo(request) as repo:
        try:
            await repo.settings.set_model(role, provider, model_id)
        except ValueError as exc:
            return error_response(str(exc), _HTTP_BAD_REQUEST)
    return _json_response(
        {
            "ok": True,
            FIELD_ROLE: role,
            FIELD_PROVIDER: provider,
            FIELD_MODEL_ID: model_id,
        }
    )


async def set_model(request: Request) -> Response:
    """Upsert a per-role model override, rejecting providers without a key."""
    parsed = await parse_json_body(request)
    if isinstance(parsed, Response):
        return parsed
    validated = validate_set_model_payload(parsed)
    if isinstance(validated, Response):
        return validated
    return await _write_override(request, *validated)
