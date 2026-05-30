"""SearXNG-backed :class:`BaseSearchClient` — self-hosted open-source metasearch.

Talks to a SearXNG instance's JSON API over ``httpx``; no API key is required,
only the base URL of the running instance.
"""

from __future__ import annotations

import httpx

from research.base_search_client import BaseSearchClient, SearchResult

_TIMEOUT_SECONDS = 10.0
_HTTP_OK = 200


def _to_result(hit: dict) -> SearchResult:
    return SearchResult(
        title=hit.get("title", ""),
        url=hit.get("url", ""),
        snippet=hit.get("content", ""),
    )


class SearXNGSearchClient(BaseSearchClient):
    """Queries a self-hosted SearXNG instance.

    Requires the instance base URL; a missing URL raises ``ValueError`` at
    construction rather than silently falling back to another provider.
    """

    def __init__(self, base_url: str | None) -> None:
        if not base_url:
            raise ValueError("SearXNG search requires SEARXNG_BASE_URL")
        self._search_url = "{0}/search".format(base_url.rstrip("/"))

    async def search(self, query: str, *, max_results: int = 5) -> list[SearchResult]:
        """GET ``query`` from the SearXNG JSON API and map the hits."""
        query_params = {"q": query, "format": "json"}
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            response = await client.get(self._search_url, params=query_params)
        if response.status_code != _HTTP_OK:
            return []
        hits = response.json().get("results", [])
        return [_to_result(hit) for hit in hits[:max_results]]
