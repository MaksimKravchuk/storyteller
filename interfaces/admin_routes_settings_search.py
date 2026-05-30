"""Admin endpoints for the operator-managed search provider + credentials.

Mirrors :mod:`interfaces.admin_routes_settings` (model overrides). The provider
selection and its credentials are persisted in ``admin_settings`` and consumed
by new-game engine builds via :func:`engine.search_settings.load_search_override`.
"""

from __future__ import annotations

from typing import Any

from aiohttp import web

from interfaces import admin_route_helpers as helpers
from interfaces.admin_routes_settings_search_helpers import (
    FIELD_PROVIDER,
    build_search_view,
    missing_search_credential,
    validate_set_search_payload,
)
from interfaces.admin_routes_settings_validation import error_response, parse_json_body

_HTTP_BAD_REQUEST = 400


async def get_search(request: web.Request) -> web.Response:
    """Report the effective search provider, its source, and credential presence."""
    cfg = helpers.get_cfg(request)
    async with helpers.open_repo(request) as repo:
        stored = await repo.settings.search_overrides()
    return helpers._json_response(build_search_view(stored, cfg))


async def _persist_search(store: Any, provider: str, tavily_api_key: str | None, searxng_base_url: str | None) -> None:
    """Write the provider and any supplied credentials (blank values are left untouched)."""
    await store.save_search("provider", provider)
    if tavily_api_key:
        await store.save_search("tavily_api_key", tavily_api_key)
    if searxng_base_url:
        await store.save_search("searxng_base_url", searxng_base_url)


async def _write_search(
    request: web.Request,
    provider: str,
    tavily_api_key: str | None,
    searxng_base_url: str | None,
) -> web.Response:
    """Persist the selection, rejecting a provider whose credential is absent."""
    async with helpers.open_repo(request) as repo:
        stored = await repo.settings.search_overrides()
        problem = missing_search_credential(
            provider,
            tavily_api_key or stored.get("tavily_api_key"),
            searxng_base_url or stored.get("searxng_base_url"),
        )
        if problem:
            return error_response(problem, _HTTP_BAD_REQUEST)
        await _persist_search(repo.settings, provider, tavily_api_key, searxng_base_url)
    return helpers._json_response({"ok": True, FIELD_PROVIDER: provider})


async def set_search(request: web.Request) -> web.Response:
    """Upsert the search provider and its credentials."""
    parsed = await parse_json_body(request)
    if isinstance(parsed, web.Response):
        return parsed
    validated = validate_set_search_payload(parsed)
    if isinstance(validated, web.Response):
        return validated
    return await _write_search(request, *validated)


async def clear_search(request: web.Request) -> web.Response:
    """Delete all stored search settings, reverting to the env/default provider."""
    async with helpers.open_repo(request) as repo:
        await repo.settings.clear_search()
    return helpers._json_response({"ok": True})
