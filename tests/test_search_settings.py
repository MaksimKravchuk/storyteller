"""Tests for engine.search_settings.load_search_override and the factory override path."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import allure
import pytest

from config import Config
from engine.factory import create_engine
from engine.search_settings import SearchSettings, load_search_override
from research.searxng_search_client import SearXNGSearchClient
from research.tavily_search_client import TavilySearchClient
from research.wikipedia_search_client import WikipediaSearchClient

pytestmark = [allure.epic("World Setup"), allure.feature("Search providers")]


@allure.story("Search override loading")
@allure.title("load_search_override maps stored rows into a SearchSettings")
@pytest.mark.asyncio
async def test_load_search_override_maps_rows() -> None:
    repo = MagicMock()
    repo.settings.search_overrides = AsyncMock(
        return_value={"provider": "tavily", "tavily_api_key": "tvly-x"},
    )
    result = await load_search_override(repo)
    assert isinstance(result, SearchSettings)
    assert result.provider == "tavily"
    assert result.tavily_api_key == "tvly-x"
    assert result.searxng_base_url is None


@allure.story("Search override loading")
@allure.title("load_search_override leaves every field None when nothing is stored")
@pytest.mark.asyncio
async def test_load_search_override_empty() -> None:
    repo = MagicMock()
    repo.settings.search_overrides = AsyncMock(return_value={})
    result = await load_search_override(repo)
    assert result == SearchSettings()


@allure.story("Factory override")
@allure.title("create_engine uses the env default search client when no override is given")
def test_create_engine_default_search_client() -> None:
    cfg = Config(openai_api_key="k")
    assert isinstance(create_engine(cfg)._search_client, WikipediaSearchClient)


@allure.story("Factory override")
@allure.title("A DB search override flips the engine's search client to the chosen provider")
def test_create_engine_search_override_flips_provider() -> None:
    cfg = Config(openai_api_key="k")
    override = SearchSettings(provider="searxng", searxng_base_url="http://searxng:8080")
    assert isinstance(create_engine(cfg, search_override=override)._search_client, SearXNGSearchClient)


@allure.story("Factory override")
@allure.title("An empty SearchSettings override falls back to the env default provider")
def test_create_engine_empty_override_falls_back() -> None:
    cfg = Config(openai_api_key="k", search_provider="wikipedia")
    assert isinstance(create_engine(cfg, search_override=SearchSettings())._search_client, WikipediaSearchClient)


@allure.story("Factory override")
@allure.title("An override provider without its own credential reuses the env credential")
def test_create_engine_override_reuses_env_credential() -> None:
    cfg = Config(openai_api_key="k", tavily_api_key="env-key")
    override = SearchSettings(provider="tavily")
    assert isinstance(create_engine(cfg, search_override=override)._search_client, TavilySearchClient)
