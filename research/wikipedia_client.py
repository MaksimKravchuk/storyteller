"""Async Wikipedia client for the Data Miner agent."""

from __future__ import annotations

import aiohttp

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
        self._session = aiohttp.ClientSession()

    async def aclose(self) -> None:
        """Close the underlying HTTP session."""
        await self._session.close()

    async def get_summary(self, title: str) -> dict[str, str]:
        """Fetch the summary (extract + description) for an article.

        Returns ``{"title": str, "extract": str, "description": str}``.
        """
        url = f"{self._rest_base}/page/summary/{title}"
        async with self._session.get(url) as resp:
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
        async with self._session.get(
            self._mw_api,
            params={
                "action": "query",
                "titles": title,
                "prop": "extracts",
                "explaintext": True,
                "exlimit": 1,
                "format": "json",
            },
        ) as resp:
            if resp.status != _HTTP_OK:
                return ""
            pages = (await resp.json()).get("query", {}).get("pages", {})
            first_page = next(iter(pages.values()), None)
            if first_page is None:
                return ""
            return first_page.get(_KEY_EXTRACT, "")[:max_chars]
