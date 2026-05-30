"""Tests for the search-provider abstraction: SearchResult, the ABC, and the factory."""

from __future__ import annotations

import dataclasses

import allure
import pytest

from research.base_search_client import BaseSearchClient, SearchResult
from research.search_factory import (
    PROVIDER_SEARXNG,
    PROVIDER_TAVILY,
    PROVIDER_WIKIPEDIA,
    create_search_client,
)
from research.searxng_search_client import SearXNGSearchClient
from research.tavily_search_client import TavilySearchClient
from research.wikipedia_search_client import WikipediaSearchClient

pytestmark = [
    allure.epic("World Setup"),
    allure.feature("Search providers"),
]


@allure.story("SearchResult contract")
@allure.title("SearchResult is a frozen three-field dataclass (title, url, snippet)")
def test_search_result_fields() -> None:
    result = SearchResult(title="T", url="u", snippet="s")
    field_names = {field.name for field in dataclasses.fields(SearchResult)}
    assert field_names == {"title", "url", "snippet"}
    assert (result.title, result.url, result.snippet) == ("T", "u", "s")


@allure.story("SearchResult contract")
@allure.title("BaseSearchClient cannot be instantiated directly (search is abstract)")
def test_base_search_client_is_abstract() -> None:
    with pytest.raises(TypeError):
        BaseSearchClient()  # type: ignore[abstract]


@allure.story("Provider routing")
@allure.title("create_search_client routes wikipedia to the zero-config Wikipedia adapter")
def test_factory_routes_wikipedia() -> None:
    assert isinstance(create_search_client(PROVIDER_WIKIPEDIA), WikipediaSearchClient)


@allure.story("Provider routing")
@allure.title("create_search_client routes tavily to TavilySearchClient when a key is present")
def test_factory_routes_tavily() -> None:
    client = create_search_client(PROVIDER_TAVILY, tavily_api_key="tvly-x")
    assert isinstance(client, TavilySearchClient)


@allure.story("Provider routing")
@allure.title("create_search_client routes searxng to SearXNGSearchClient when a base URL is present")
def test_factory_routes_searxng() -> None:
    client = create_search_client(PROVIDER_SEARXNG, searxng_base_url="http://localhost:8888")
    assert isinstance(client, SearXNGSearchClient)


@allure.story("Provider routing")
@allure.title("create_search_client raises ValueError for an unknown provider")
def test_factory_unknown_provider_raises() -> None:
    with pytest.raises(ValueError, match="Unknown search provider"):
        create_search_client("bing")


@allure.story("Fail-fast configuration")
@allure.title("Selecting tavily without TAVILY_API_KEY raises at construction (no silent Wikipedia fallback)")
def test_factory_tavily_missing_key_raises() -> None:
    with pytest.raises(ValueError, match="TAVILY_API_KEY"):
        create_search_client(PROVIDER_TAVILY, tavily_api_key=None)


@allure.story("Fail-fast configuration")
@allure.title("Selecting searxng without SEARXNG_BASE_URL raises at construction (no silent Wikipedia fallback)")
def test_factory_searxng_missing_url_raises() -> None:
    with pytest.raises(ValueError, match="SEARXNG_BASE_URL"):
        create_search_client(PROVIDER_SEARXNG, searxng_base_url=None)
