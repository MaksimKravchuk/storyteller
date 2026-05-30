"""Tavily-backed :class:`BaseSearchClient` — hosted AI search.

Uses a raw ``httpx`` POST rather than the Tavily SDK so the integration adds
no new dependency (``httpx`` is already a project dependency).
"""

from __future__ import annotations

import httpx

from research.base_search_client import BaseSearchClient, SearchResult

_TAVILY_URL = "https://api.tavily.com/search"
_TIMEOUT_SECONDS = 10.0
_HTTP_OK = 200


def _to_result(hit: dict) -> SearchResult:
    return SearchResult(
        title=hit.get("title", ""),
        url=hit.get("url", ""),
        snippet=hit.get("content", ""),
    )


class TavilySearchClient(BaseSearchClient):
    """Queries the Tavily search API.

    Requires an API key; a missing key raises ``ValueError`` at construction
    rather than silently falling back to another provider.
    """

    def __init__(self, api_key: str | None) -> None:
        if not api_key:
            raise ValueError("Tavily search requires TAVILY_API_KEY")
        self._api_key = api_key

    async def search(self, query: str, *, max_results: int = 5) -> list[SearchResult]:
        """POST ``query`` to Tavily and map the hits into search results."""
        payload = {"api_key": self._api_key, "query": query, "max_results": max_results}
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            response = await client.post(_TAVILY_URL, json=payload)
        if response.status_code != _HTTP_OK:
            return []
        hits = response.json().get("results", [])
        return [_to_result(hit) for hit in hits[:max_results]]
