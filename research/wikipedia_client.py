"""Async Wikipedia client for the Data Miner agent."""

from __future__ import annotations

import aiohttp

WIKIPEDIA_REST_BASE = "https://en.wikipedia.org/api/rest_v1"
WIKIPEDIA_MW_API = "https://en.wikipedia.org/w/api.php"

_HTTP_OK = 200
_KEY_EXTRACT = "extract"


class WikipediaClient:
    """Lightweight async client for the Wikipedia REST / MediaWiki APIs.

    Used by the Data Miner to ground game settings in real historical data.
    """

    def __init__(self, language: str = "en") -> None:
        self._lang = language
        self._rest_base = f"https://{language}.wikipedia.org/api/rest_v1"
        self._mw_api = f"https://{language}.wikipedia.org/w/api.php"

    async def search(self, query: str, limit: int = 5) -> list[str]:
        """Search Wikipedia and return matching article titles."""
        query_params = {
            "action": "opensearch",
            "search": query,
            "limit": limit,
            "format": "json",
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(self._mw_api, params=query_params) as resp:
                if resp.status == _HTTP_OK:
                    search_json = await resp.json()
                    return search_json[1] if len(search_json) > 1 else []
                return []

    async def get_summary(self, title: str) -> dict[str, str]:
        """Fetch the summary (extract + description) for an article.

        Returns ``{"title": str, "extract": str, "description": str}``.
        """
        url = f"{self._rest_base}/page/summary/{title}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == _HTTP_OK:
                    summary_json = await resp.json()
                    return {
                        "title": summary_json.get("title", title),
                        _KEY_EXTRACT: summary_json.get(_KEY_EXTRACT, ""),
                        "description": summary_json.get("description", ""),
                    }
                return {
                    "title": title,
                    _KEY_EXTRACT: "",
                    "description": "Article not found",
                }

    async def get_full_article(self, title: str, max_chars: int = 5000) -> str:
        """Fetch the full plain-text content of an article, truncated.

        Uses the MediaWiki API ``extracts`` module.
        """
        query_params = {
            "action": "query",
            "titles": title,
            "prop": "extracts",
            "explaintext": True,
            "exlimit": 1,
            "format": "json",
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(self._mw_api, params=query_params) as resp:
                if resp.status != _HTTP_OK:
                    return ""
                article_json = await resp.json()
                pages = article_json.get("query", {}).get("pages", {})
                for page in pages.values():
                    text = page.get(_KEY_EXTRACT, "")
                    return text[:max_chars]
                return ""
