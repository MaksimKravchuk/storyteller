"""Validation + view helpers for the admin search-provider settings endpoints."""

from __future__ import annotations

from typing import Any, Union

from aiohttp import web

from db.repo_settings_search import ALLOWED_SEARCH_PROVIDERS
from interfaces.admin_routes_settings_validation import error_response
from research.search_factory import PROVIDER_SEARXNG, PROVIDER_TAVILY

_HTTP_BAD_REQUEST = 400

FIELD_PROVIDER = "provider"
FIELD_TAVILY_API_KEY = "tavily_api_key"
FIELD_SEARXNG_BASE_URL = "searxng_base_url"

_ValidatedSearch = tuple[str, str | None, str | None]
_ValidationOutcome = Union[_ValidatedSearch, web.Response]


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
        FIELD_PROVIDER: stored.get("provider") or cfg.search_provider,
        "source": "db" if stored.get("provider") else "env",
        "providers": sorted(ALLOWED_SEARCH_PROVIDERS),
        "tavily_api_key_set": bool(stored.get("tavily_api_key") or cfg.tavily_api_key),
        FIELD_SEARXNG_BASE_URL: stored.get("searxng_base_url") or cfg.searxng_base_url or "",
    }
