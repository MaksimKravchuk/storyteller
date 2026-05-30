"""Opt-in live smoke test for the Tavily search backend.

Marked ``live`` so it is excluded from the default suite (see the
``addopts`` filter in ``pyproject.toml``) and skipped unless
``TAVILY_API_KEY`` is set. It only runs in the dedicated CI step that
injects the secret — it hits the real Tavily API with no network mocking,
proving the integration end-to-end (CI green on stubs alone is insufficient
for a ``research/`` live integration per the Demo Contract).
"""

from __future__ import annotations

import os

import allure
import pytest

from research.base_search_client import SearchResult
from research.search_factory import create_search_client

pytestmark = [
    allure.epic("World Setup"),
    allure.feature("Search providers"),
    pytest.mark.live,
    pytest.mark.skipif(not os.environ.get("TAVILY_API_KEY"), reason="TAVILY_API_KEY not set"),
]


@allure.story("Tavily live integration")
@allure.title("TavilySearchClient returns real SearchResults from the live Tavily API")
@pytest.mark.asyncio
async def test_tavily_live_search_returns_results() -> None:
    client = create_search_client("tavily", tavily_api_key=os.environ["TAVILY_API_KEY"])
    results = await client.search("Renaissance Florence Medici banking", max_results=3)
    assert results, "live Tavily search returned no results"
    assert all(isinstance(hit, SearchResult) for hit in results)
    assert any(hit.snippet for hit in results), "expected at least one non-empty snippet"
