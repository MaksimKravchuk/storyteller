"""Coverage for interfaces.admin_routes_settings_search — the search provider endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import allure
import pytest
from fastapi import FastAPI
from starlette.responses import Response

from config import Config
from tests.admin_app import admin_client, make_admin_app
from interfaces.admin_routes_settings_search import (
    build_search_view,
    missing_search_credential,
    validate_set_search_payload,
)

pytestmark = [
    allure.epic("Player Interfaces"),
    allure.feature("Admin settings routes"),
]

_HTTP_OK = 200
_HTTP_BAD_REQUEST = 400
_API_SEARCH = "/api/settings/search"


def _make_app(cfg: Config) -> FastAPI:
    return make_admin_app(cfg)


def _repo_with(stored: dict) -> AsyncMock:
    repo = AsyncMock()
    repo.settings.search_overrides.return_value = stored
    return repo


def _prime_get_db(mock_get_db) -> None:
    mock_get_db.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
    mock_get_db.return_value.__aexit__ = AsyncMock(return_value=False)


def _patched(repo: AsyncMock):
    return (
        patch("interfaces.admin_route_helpers.get_db"),
        patch("interfaces.admin_route_helpers.GameRepository", return_value=repo),
    )


@allure.story("Search settings API")
@allure.title("GET /api/settings/search reports the env default when nothing is stored")
@pytest.mark.asyncio
async def test_get_search_default() -> None:
    repo = _repo_with({})
    get_db_patch, repo_patch = _patched(repo)
    async with admin_client(_make_app(Config(openai_api_key="k", tavily_api_key=None))) as client:
        with get_db_patch as mock_get_db, repo_patch:
            _prime_get_db(mock_get_db)
            resp = await client.get(_API_SEARCH)
            body = resp.json()
    assert body["provider"] == "wikipedia"
    assert body["source"] == "env"
    assert body["tavily_api_key_set"] is False


@allure.story("Search settings API")
@allure.title("GET /api/settings/search never echoes the stored Tavily key back")
@pytest.mark.asyncio
async def test_get_search_masks_secret() -> None:
    repo = _repo_with({"provider": "tavily", "tavily_api_key": "tvly-super-secret"})
    get_db_patch, repo_patch = _patched(repo)
    async with admin_client(_make_app(Config(openai_api_key="k"))) as client:
        with get_db_patch as mock_get_db, repo_patch:
            _prime_get_db(mock_get_db)
            resp = await client.get(_API_SEARCH)
            body = resp.json()
    assert body["provider"] == "tavily"
    assert body["source"] == "db"
    assert body["tavily_api_key_set"] is True
    assert "tvly-super-secret" not in str(body)


@allure.story("Search settings API")
@allure.title("POST /api/settings/search persists the provider and the supplied credential")
@pytest.mark.asyncio
async def test_set_search_tavily_with_key() -> None:
    repo = _repo_with({})
    get_db_patch, repo_patch = _patched(repo)
    async with admin_client(_make_app(Config(openai_api_key="k"))) as client:
        with get_db_patch as mock_get_db, repo_patch:
            _prime_get_db(mock_get_db)
            resp = await client.post(_API_SEARCH, json={"provider": "tavily", "tavily_api_key": "tvly-x"})
            assert resp.status_code == _HTTP_OK
    repo.settings.save_search.assert_any_await("provider", "tavily")
    repo.settings.save_search.assert_any_await("tavily_api_key", "tvly-x")


@allure.story("Search settings API")
@allure.title("POST /api/settings/search rejects tavily with no key available (400)")
@pytest.mark.asyncio
async def test_set_search_tavily_missing_key() -> None:
    repo = _repo_with({})
    get_db_patch, repo_patch = _patched(repo)
    async with admin_client(_make_app(Config(openai_api_key="k"))) as client:
        with get_db_patch as mock_get_db, repo_patch:
            _prime_get_db(mock_get_db)
            resp = await client.post(_API_SEARCH, json={"provider": "tavily"})
            assert resp.status_code == _HTTP_BAD_REQUEST
    repo.settings.save_search.assert_not_awaited()


@allure.story("Search settings API")
@allure.title("POST /api/settings/search rejects an unknown provider (400)")
@pytest.mark.asyncio
async def test_set_search_invalid_provider() -> None:
    repo = _repo_with({})
    get_db_patch, repo_patch = _patched(repo)
    async with admin_client(_make_app(Config(openai_api_key="k"))) as client:
        with get_db_patch as mock_get_db, repo_patch:
            _prime_get_db(mock_get_db)
            resp = await client.post(_API_SEARCH, json={"provider": "bing"})
            assert resp.status_code == _HTTP_BAD_REQUEST


@allure.story("Search settings API")
@allure.title("DELETE /api/settings/search clears the stored settings")
@pytest.mark.asyncio
async def test_clear_search() -> None:
    repo = _repo_with({"provider": "tavily"})
    get_db_patch, repo_patch = _patched(repo)
    async with admin_client(_make_app(Config(openai_api_key="k"))) as client:
        with get_db_patch as mock_get_db, repo_patch:
            _prime_get_db(mock_get_db)
            resp = await client.delete(_API_SEARCH)
            assert resp.status_code == _HTTP_OK
    repo.settings.clear_search.assert_awaited_once()


@allure.story("Search settings helpers")
@allure.title("validate_set_search_payload accepts a valid provider and normalises blanks to None")
def test_validate_payload_ok() -> None:
    assert validate_set_search_payload({"provider": "wikipedia", "tavily_api_key": "  "}) == ("wikipedia", None, None)


@allure.story("Search settings helpers")
@allure.title("validate_set_search_payload rejects an unknown provider and non-string credentials")
def test_validate_payload_rejects() -> None:
    assert isinstance(validate_set_search_payload({"provider": "bing"}), Response)
    assert isinstance(validate_set_search_payload({"provider": "tavily", "tavily_api_key": 5}), Response)


@allure.story("Search settings helpers")
@allure.title("missing_search_credential flags providers that lack their required credential")
def test_missing_credential() -> None:
    assert missing_search_credential("tavily", None, None)
    assert missing_search_credential("searxng", None, None)
    assert missing_search_credential("tavily", "key", None) is None
    assert missing_search_credential("wikipedia", None, None) is None


@allure.story("Search settings helpers")
@allure.title("build_search_view masks the key and reports the DB source when stored")
def test_build_view_masks_and_sources() -> None:
    view = build_search_view({"provider": "tavily", "tavily_api_key": "secret"}, Config(openai_api_key="k"))
    assert view["provider"] == "tavily"
    assert view["source"] == "db"
    assert view["tavily_api_key_set"] is True
    assert "secret" not in str(view)
