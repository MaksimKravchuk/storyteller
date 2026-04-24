"""Admin endpoints for API-key status and per-role model overrides."""

from __future__ import annotations

from aiohttp import web

from config import get_api_key_for_provider, list_api_key_status
from interfaces import admin_route_helpers as helpers
from interfaces.admin_routes_settings_helpers import build_catalog, merge_role_entries
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


async def get_keys(request: web.Request) -> web.Response:
    """Report ``{provider: bool}`` — whether each provider's API key is set."""
    cfg = helpers.get_cfg(request)
    return helpers._json_response(list_api_key_status(cfg))


async def get_models(request: web.Request) -> web.Response:
    """Report current effective model per role plus the UI catalog."""
    cfg = helpers.get_cfg(request)
    async with helpers.open_repo(request) as repo:
        db_overrides = await repo.settings.get_model_overrides()
    return helpers._json_response(
        {
            "roles": merge_role_entries(db_overrides, cfg),
            "catalog": build_catalog(),
        }
    )


async def _write_override(
    request: web.Request,
    role: str,
    provider: str,
    model_id: str,
) -> web.Response:
    """Persist the override and return the success payload, or a 4xx response."""
    if not get_api_key_for_provider(provider, helpers.get_cfg(request)):
        return error_response("no api key configured for provider {0}".format(provider), _HTTP_CONFLICT)
    async with helpers.open_repo(request) as repo:
        try:
            await repo.settings.set_model(role, provider, model_id)
        except ValueError as exc:
            return error_response(str(exc), _HTTP_BAD_REQUEST)
    return helpers._json_response(
        {
            "ok": True,
            FIELD_ROLE: role,
            FIELD_PROVIDER: provider,
            FIELD_MODEL_ID: model_id,
        }
    )


async def set_model(request: web.Request) -> web.Response:
    """Upsert a per-role model override, rejecting providers without a key."""
    parsed = await parse_json_body(request)
    if isinstance(parsed, web.Response):
        return parsed
    validated = validate_set_model_payload(parsed)
    if isinstance(validated, web.Response):
        return validated
    return await _write_override(request, *validated)
