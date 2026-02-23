"""Async Wikipedia client for the Data Miner agent."""

from __future__ import annotations

import aiohttp


class WikipediaClient:
    """Lightweight async client for the Wikipedia REST / MediaWiki APIs.

    Used by the Data Miner to ground game settings in real historical data.
    """

    REST_BASE = "https://en.wikipedia.org/api/rest_v1"
    MW_API = "https://en.wikipedia.org/w/api.php"

    def __init__(self, language: str = "en") -> None:
        self._lang = language
        self._rest_base = f"https://{language}.wikipedia.org/api/rest_v1"
        self._mw_api = f"https://{language}.wikipedia.org/w/api.php"

    async def search(self, query: str, limit: int = 5) -> list[str]:
        """Search Wikipedia and return matching article titles."""
        params = {
            "action": "opensearch",
            "search": query,
            "limit": limit,
            "format": "json",
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(self._mw_api, params=params) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data[1] if len(data) > 1 else []
                return []

    async def get_summary(self, title: str) -> dict[str, str]:
        """Fetch the summary (extract + description) for an article.

        Returns ``{"title": str, "extract": str, "description": str}``.
        """
        url = f"{self._rest_base}/page/summary/{title}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {
                        "title": data.get("title", title),
                        "extract": data.get("extract", ""),
                        "description": data.get("description", ""),
                    }
                return {
                    "title": title,
                    "extract": "",
                    "description": "Article not found",
                }

    async def get_full_article(
        self, title: str, max_chars: int = 5000
    ) -> str:
        """Fetch the full plain-text content of an article, truncated.

        Uses the MediaWiki API ``extracts`` module.
        """
        params = {
            "action": "query",
            "titles": title,
            "prop": "extracts",
            "explaintext": True,
            "exlimit": 1,
            "format": "json",
        }
        async with aiohttp.ClientSession() as session:
            async with session.get(self._mw_api, params=params) as resp:
                if resp.status != 200:
                    return ""
                data = await resp.json()
                pages = data.get("query", {}).get("pages", {})
                for page in pages.values():
                    text = page.get("extract", "")
                    return text[:max_chars]
                return ""
