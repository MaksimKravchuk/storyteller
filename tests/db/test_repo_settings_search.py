"""DB-backed tests for the search-provider settings on AdminSettingsStore."""

from __future__ import annotations

import allure
import pytest

from db.repository import GameRepository

pytestmark = [allure.epic("Admin Dashboard"), allure.feature("Settings persistence"), pytest.mark.db]


@allure.story("Search settings persistence")
@allure.title("search_overrides returns an empty dict on a fresh table")
@pytest.mark.asyncio
async def test_empty_returns_empty(db_session) -> None:
    store = GameRepository(db_session).settings
    assert await store.search_overrides() == {}


@allure.story("Search settings persistence")
@allure.title("save_search inserts a provider row and search_overrides reads it back")
@pytest.mark.asyncio
async def test_set_and_get_roundtrip(db_session) -> None:
    store = GameRepository(db_session).settings
    await store.save_search("provider", "tavily")
    assert (await store.search_overrides())["provider"] == "tavily"


@allure.story("Search settings persistence")
@allure.title("save_search upserts the same field idempotently")
@pytest.mark.asyncio
async def test_set_search_updates_existing(db_session) -> None:
    store = GameRepository(db_session).settings
    await store.save_search("provider", "tavily")
    await store.save_search("provider", "searxng")
    assert (await store.search_overrides())["provider"] == "searxng"


@allure.story("Search settings persistence")
@allure.title("provider and both credentials round-trip together")
@pytest.mark.asyncio
async def test_credentials_roundtrip(db_session) -> None:
    store = GameRepository(db_session).settings
    await store.save_search("provider", "tavily")
    await store.save_search("tavily_api_key", "tvly-x")
    await store.save_search("searxng_base_url", "http://searxng:8080")
    assert await store.search_overrides() == {
        "provider": "tavily",
        "tavily_api_key": "tvly-x",
        "searxng_base_url": "http://searxng:8080",
    }


@allure.story("Search settings persistence")
@allure.title("clear_search deletes every stored search setting")
@pytest.mark.asyncio
async def test_clear_deletes(db_session) -> None:
    store = GameRepository(db_session).settings
    await store.save_search("provider", "tavily")
    await store.save_search("tavily_api_key", "tvly-x")
    await store.clear_search()
    assert await store.search_overrides() == {}


@allure.story("Search settings persistence")
@allure.title("save_search rejects an unknown field, provider, or empty value")
@pytest.mark.asyncio
async def test_set_search_validation(db_session) -> None:
    store = GameRepository(db_session).settings
    with pytest.raises(ValueError, match="unknown search field"):
        await store.save_search("nonsense", "x")
    with pytest.raises(ValueError, match="unknown search provider"):
        await store.save_search("provider", "bing")
    with pytest.raises(ValueError, match="search value must be"):
        await store.save_search("provider", "")
