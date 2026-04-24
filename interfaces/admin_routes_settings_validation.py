"""Payload-validation helpers for the admin model-settings endpoints."""

from __future__ import annotations

import json
from typing import Any, Union

from aiohttp import web

from db import repo_settings
from interfaces.admin_route_helpers import _json_response

_HTTP_BAD_REQUEST = 400

FIELD_ROLE = "role"
FIELD_PROVIDER = "provider"
FIELD_MODEL_ID = "model_id"

_ValidatedTriple = tuple[str, str, str]
_ValidationOutcome = Union[_ValidatedTriple, web.Response]


def error_response(message: str, status: int) -> web.Response:
    """Return a JSON error payload wrapped in an aiohttp response."""
    return _json_response({"error": message}, status=status)


async def parse_json_body(request: web.Request) -> dict[str, Any] | web.Response:
    """Parse the request body as a JSON object, or return a 400 response."""
    try:
        payload = await request.json()
    except json.JSONDecodeError:
        return error_response("invalid JSON body", _HTTP_BAD_REQUEST)
    if not isinstance(payload, dict):
        return error_response("body must be a JSON object", _HTTP_BAD_REQUEST)
    return payload


def _field_is_valid(field_name: str, field_value: Any) -> bool:
    if field_name == FIELD_ROLE:
        return isinstance(field_value, str) and field_value in repo_settings.ALLOWED_ROLES
    if field_name == FIELD_PROVIDER:
        return isinstance(field_value, str) and field_value in repo_settings.ALLOWED_PROVIDERS
    return isinstance(field_value, str) and bool(field_value.strip())


def _pick_first_invalid(payload: dict[str, Any]) -> str | None:
    """Return the name of the first invalid field, or ``None`` if all pass."""
    for field_name in (FIELD_ROLE, FIELD_PROVIDER, FIELD_MODEL_ID):
        if not _field_is_valid(field_name, payload.get(field_name)):
            return field_name
    return None


def validate_set_model_payload(payload: dict[str, Any]) -> _ValidationOutcome:
    """Extract & validate (role, provider, model_id); return a 400 on any failure."""
    bad_field = _pick_first_invalid(payload)
    if bad_field is not None:
        return error_response("invalid {0}".format(bad_field), _HTTP_BAD_REQUEST)
    role: str = payload[FIELD_ROLE]
    provider: str = payload[FIELD_PROVIDER]
    model_id: str = payload[FIELD_MODEL_ID].strip()
    return role, provider, model_id
