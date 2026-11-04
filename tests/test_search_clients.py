"""Tests for the concrete search clients (Wikipedia adapter, Tavily, SearXNG).

The Tavily/SearXNG cases use a hand-rolled async ``httpx.AsyncClient`` fake,
sharing the fake pattern of ``tests/test_wikipedia_client.py`` — no
network is touched.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import allure
import pytest

from research.base_search_client import SearchResult
from research.searxng_search_client import SearXNGSearchClient
from research.tavily_search_client import TavilySearchClient
from research.wikipedia_client import WikipediaClient
from research.wikipedia_search_client import WikipediaSearchClient

pytestmark = [
    allure.epic("World Setup"),
    allure.feature("Search providers"),
]

_HTTP_OK = 200
_HTTP_ERROR = 500


class _FakeResponse:
    """Stand-in for an ``httpx.Response`` (``status_code`` + sync ``json``)."""

    def __init__(self, status_code: int, payload: object) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> object:
        return self._payload


class _FakeAsyncClient:
    """Async-context-manager fake replacing ``httpx.AsyncClient``."""

    def __init__(self, response: _FakeResponse, recorder: dict | None = None) -> None:
        self._response = response
        self._recorder = {} if recorder is None else recorder

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False

    async def post(self, url: str, json: object = None) -> _FakeResponse:
        self._recorder["url"] = url
        self._recorder["json"] = json
        return self._response

    async def get(self, url: str, params: object = None) -> _FakeResponse:
        self._recorder["url"] = url
        self._recorder["params"] = params
        return self._response


def _patch_httpx(module: str, response: _FakeResponse, recorder: dict | None = None):
    return patch("{0}.httpx.AsyncClient".format(module), return_value=_FakeAsyncClient(response, recorder))


@allure.story("Wikipedia adapter")
@allure.title("WikipediaSearchClient exposes the underlying client and its get_summary for ensure_fact")
def test_wikipedia_adapter_exposes_underlying_client() -> None:
    stub = MagicMock(spec=WikipediaClient)
    adapter = WikipediaSearchClient(stub)
    assert adapter.wikipedia is stub
    assert hasattr(adapter, "wikipedia")


@allure.story("Wikipedia adapter")
@allure.title("WikipediaSearchClient.search wraps the article extract into a single SearchResult")
@pytest.mark.asyncio
async def test_wikipedia_adapter_search_wraps_extract() -> None:
    stub = MagicMock(spec=WikipediaClient)
    stub.get_summary = AsyncMock(return_value={"title": "Rome", "extract": "The eternal city.", "description": "d"})
    results = await WikipediaSearchClient(stub).search("Rome")
    assert results == [
        SearchResult(title="Rome", url="https://en.wikipedia.org/wiki/Rome", snippet="The eternal city.")
    ]
    stub.get_summary.assert_awaited_once_with("Rome")


@allure.story("Wikipedia adapter")
@allure.title("WikipediaSearchClient.search returns an empty list when the article has no extract")
@pytest.mark.asyncio
async def test_wikipedia_adapter_search_empty_extract() -> None:
    stub = MagicMock(spec=WikipediaClient)
    stub.get_summary = AsyncMock(return_value={"title": "X", "extract": "", "description": "Article not found"})
    assert await WikipediaSearchClient(stub).search("X") == []


@allure.story("Tavily adapter")
@allure.title("TavilySearchClient maps a 200 response into SearchResult objects, capped at max_results")
@pytest.mark.asyncio
async def test_tavily_search_maps_results() -> None:
    payload = {
        "results": [
            {"title": "A", "url": "ua", "content": "snippet a"},
            {"title": "B", "url": "ub", "content": "snippet b"},
            {"title": "C", "url": "uc", "content": "snippet c"},
        ],
    }
    recorder: dict = {}
    with _patch_httpx("research.tavily_search_client", _FakeResponse(_HTTP_OK, payload), recorder):
        results = await TavilySearchClient("tvly-x").search("Florence", max_results=2)
    assert results == [
        SearchResult(title="A", url="ua", snippet="snippet a"),
        SearchResult(title="B", url="ub", snippet="snippet b"),
    ]
    assert recorder["json"]["query"] == "Florence"
    assert recorder["json"]["api_key"] == "tvly-x"


@allure.story("Tavily adapter")
@allure.title("TavilySearchClient returns an empty list on a non-200 response without raising")
@pytest.mark.asyncio
async def test_tavily_search_non_200_returns_empty() -> None:
    with _patch_httpx("research.tavily_search_client", _FakeResponse(_HTTP_ERROR, None)):
        assert await TavilySearchClient("tvly-x").search("Florence") == []


@allure.story("Tavily adapter")
@allure.title("TavilySearchClient with no API key raises ValueError at construction")
def test_tavily_missing_key_raises() -> None:
    with pytest.raises(ValueError, match="TAVILY_API_KEY"):
        TavilySearchClient(None)


@allure.story("SearXNG adapter")
@allure.title("SearXNGSearchClient maps a 200 JSON response into SearchResult objects via the /search endpoint")
@pytest.mark.asyncio
async def test_searxng_search_maps_results() -> None:
    payload = {"results": [{"title": "A", "url": "ua", "content": "snippet a"}]}
    recorder: dict = {}
    with _patch_httpx("research.searxng_search_client", _FakeResponse(_HTTP_OK, payload), recorder):
        results = await SearXNGSearchClient("http://localhost:8888/").search("Florence")
    assert results == [SearchResult(title="A", url="ua", snippet="snippet a")]
    assert recorder["url"] == "http://localhost:8888/search"
    assert recorder["params"] == {"q": "Florence", "format": "json"}


@allure.story("SearXNG adapter")
@allure.title("SearXNGSearchClient returns an empty list on a non-200 response without raising")
@pytest.mark.asyncio
async def test_searxng_search_non_200_returns_empty() -> None:
    with _patch_httpx("research.searxng_search_client", _FakeResponse(_HTTP_ERROR, None)):
        assert await SearXNGSearchClient("http://localhost:8888").search("Florence") == []


@allure.story("SearXNG adapter")
@allure.title("SearXNGSearchClient with no base URL raises ValueError at construction")
def test_searxng_missing_url_raises() -> None:
    with pytest.raises(ValueError, match="SEARXNG_BASE_URL"):
        SearXNGSearchClient(None)
