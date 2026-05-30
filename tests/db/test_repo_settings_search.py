"""DB-backed tests for the search-provider settings on AdminSettingsStore."""

from __future__ import annotations

import allure
import pytest

pytestmark = [
    pytest.mark.db,
    allure.epic("Admin panel"),
    allure.feature("Search provider settings"),
]


@allure.story("Empty store")
@allure.title("search_overrides returns an empty dict when nothing is stored")
@pytest.mark.asyncio
async def test_empty_returns_empty(repo) -> None:
    assert await repo.settings.search_overrides() == {}


@allure.story("Upsert")
@allure.title("save_search inserts a provider row and search_overrides reads it back")
@pytest.mark.asyncio
async def test_set_and_get_roundtrip(repo) -> None:
    await repo.settings.save_search("provider", "tavily")
    assert (await repo.settings.search_overrides())["provider"] == "tavily"


@allure.story("Upsert")
@allure.title("save_search upserts the same field idempotently")
@pytest.mark.asyncio
async def test_set_search_updates_existing(repo) -> None:
    await repo.settings.save_search("provider", "tavily")
    await repo.settings.save_search("provider", "searxng")
    assert (await repo.settings.search_overrides())["provider"] == "searxng"


@allure.story("Upsert")
@allure.title("provider and both credentials round-trip together")
@pytest.mark.asyncio
async def test_credentials_roundtrip(repo) -> None:
    await repo.settings.save_search("provider", "tavily")
    await repo.settings.save_search("tavily_api_key", "tvly-x")
    await repo.settings.save_search("searxng_base_url", "http://searxng:8080")
    assert await repo.settings.search_overrides() == {
        "provider": "tavily",
        "tavily_api_key": "tvly-x",
        "searxng_base_url": "http://searxng:8080",
    }


@allure.story("Clear")
@allure.title("clear_search deletes every stored search setting")
@pytest.mark.asyncio
async def test_clear_deletes(repo) -> None:
    await repo.settings.save_search("provider", "tavily")
    await repo.settings.save_search("tavily_api_key", "tvly-x")
    await repo.settings.clear_search()
    assert await repo.settings.search_overrides() == {}


@allure.story("Validation")
@allure.title("save_search rejects an unknown field, provider, or empty value")
@pytest.mark.asyncio
async def test_set_search_validation(repo) -> None:
    with pytest.raises(ValueError, match="unknown search field"):
        await repo.settings.save_search("nonsense", "x")
    with pytest.raises(ValueError, match="unknown search provider"):
        await repo.settings.save_search("provider", "bing")
    with pytest.raises(ValueError, match="search value must be"):
        await repo.settings.save_search("provider", "")
