"""Admin endpoints for the operator-managed search provider + credentials.

Mirrors :mod:`interfaces.admin_routes_settings` (model overrides). The provider
selection and its credentials are persisted in ``admin_settings`` and consumed
by new-game engine builds via :func:`engine.search_settings.load_search_override`.
"""

from __future__ import annotations

from typing import Any, Union

from fastapi import Request
from starlette.responses import Response

from interfaces.admin_json import _json_response
from interfaces import admin_route_helpers as helpers
from db.repo_settings_search import ALLOWED_SEARCH_PROVIDERS
from interfaces.admin_routes_settings_validation import error_response, parse_json_body
from research.search_factory import PROVIDER_SEARXNG, PROVIDER_TAVILY

_HTTP_BAD_REQUEST = 400

FIELD_PROVIDER = "provider"
FIELD_TAVILY_API_KEY = "tavily_api_key"
FIELD_SEARXNG_BASE_URL = "searxng_base_url"

_ValidatedSearch = tuple[str, str | None, str | None]
_ValidationOutcome = Union[_ValidatedSearch, Response]


def _is_provider(raw: Any) -> bool:
    return isinstance(raw, str) and raw in ALLOWED_SEARCH_PROVIDERS


def _is_optional_str(raw: Any) -> bool:
    return raw is None or isinstance(raw, str)


def _norm(raw: Any) -> str | None:
    return (raw or "").strip() or None


def validate_set_search_payload(payload: dict[str, Any]) -> _ValidationOutcome:
    """Extract & validate (provider, tavily_api_key, searxng_base_url) or return a 400."""
    if not _is_provider(payload.get(FIELD_PROVIDER)):
        return error_response("invalid {0}".format(FIELD_PROVIDER), _HTTP_BAD_REQUEST)
    tavily = payload.get(FIELD_TAVILY_API_KEY)
    searxng = payload.get(FIELD_SEARXNG_BASE_URL)
    if not _is_optional_str(tavily) or not _is_optional_str(searxng):
        return error_response("credentials must be strings", _HTTP_BAD_REQUEST)
    provider_name: str = payload[FIELD_PROVIDER]
    return provider_name, _norm(tavily), _norm(searxng)


def missing_search_credential(provider: str, tavily_key: str | None, searxng_url: str | None) -> str | None:
    """Return an error message when the chosen provider lacks its required credential."""
    if provider == PROVIDER_TAVILY and not tavily_key:
        return "{0} required for tavily".format(FIELD_TAVILY_API_KEY)
    if provider == PROVIDER_SEARXNG and not searxng_url:
        return "{0} required for searxng".format(FIELD_SEARXNG_BASE_URL)
    return None


def build_search_view(stored: dict[str, str], cfg: Any) -> dict[str, Any]:
    """Build the masked admin view: provider + source + credential presence.

    The Tavily API key is never echoed back — only whether one is configured.
    The SearXNG base URL is not a secret, so it is returned in clear.
    """
    return {
        FIELD_PROVIDER: stored.get(FIELD_PROVIDER) or cfg.search_provider,
        "source": "db" if stored.get(FIELD_PROVIDER) else "env",
        "providers": sorted(ALLOWED_SEARCH_PROVIDERS),
        "tavily_api_key_set": bool(stored.get(FIELD_TAVILY_API_KEY) or cfg.tavily_api_key),
        FIELD_SEARXNG_BASE_URL: stored.get(FIELD_SEARXNG_BASE_URL) or cfg.searxng_base_url or "",
    }


async def get_search(request: Request) -> Response:
    """Report the effective search provider, its source, and credential presence."""
    cfg = helpers.get_cfg(request)
    async with helpers.open_repo(request) as repo:
        stored = await repo.settings.search_overrides()
    return _json_response(build_search_view(stored, cfg))


async def _persist_search(store: Any, provider: str, tavily_api_key: str | None, searxng_base_url: str | None) -> None:
    """Write the provider and any supplied credentials (blank values are left untouched)."""
    await store.save_search(FIELD_PROVIDER, provider)
    if tavily_api_key:
        await store.save_search(FIELD_TAVILY_API_KEY, tavily_api_key)
    if searxng_base_url:
        await store.save_search(FIELD_SEARXNG_BASE_URL, searxng_base_url)


async def _write_search(
    request: Request,
    provider: str,
    tavily_api_key: str | None,
    searxng_base_url: str | None,
) -> Response:
    """Persist the selection, rejecting a provider whose credential is absent."""
    async with helpers.open_repo(request) as repo:
        stored = await repo.settings.search_overrides()
        problem = missing_search_credential(
            provider,
            tavily_api_key or stored.get(FIELD_TAVILY_API_KEY),
            searxng_base_url or stored.get(FIELD_SEARXNG_BASE_URL),
        )
        if problem:
            return error_response(problem, _HTTP_BAD_REQUEST)
        await _persist_search(repo.settings, provider, tavily_api_key, searxng_base_url)
    return _json_response({"ok": True, FIELD_PROVIDER: provider})


async def set_search(request: Request) -> Response:
    """Upsert the search provider and its credentials."""
    parsed = await parse_json_body(request)
    if isinstance(parsed, Response):
        return parsed
    validated = validate_set_search_payload(parsed)
    if isinstance(validated, Response):
        return validated
    return await _write_search(request, *validated)


async def clear_search(request: Request) -> Response:
    """Delete all stored search settings, reverting to the env/default provider."""
    async with helpers.open_repo(request) as repo:
        await repo.settings.clear_search()
    return _json_response({"ok": True})
