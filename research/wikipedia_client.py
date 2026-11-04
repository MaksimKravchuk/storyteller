"""Async Wikipedia client for the Data Miner agent."""

from __future__ import annotations

import httpx

_HTTP_OK = 200
_TIMEOUT_SECONDS = 10.0
_KEY_EXTRACT = "extract"


class WikipediaClient:
    """Lightweight async client for the Wikipedia REST / MediaWiki APIs.

    Used by the Data Miner to ground game settings in real historical data.
    """

    def __init__(self, language: str = "en") -> None:
        self._lang = language
        self._rest_base = f"https://{language}.wikipedia.org/api/rest_v1"
        self._mw_api = f"https://{language}.wikipedia.org/w/api.php"

    async def get_summary(self, title: str) -> dict[str, str]:
        """Fetch the summary (extract + description) for an article.

        Returns ``{"title": str, "extract": str, "description": str}``.
        """
        url = f"{self._rest_base}/page/summary/{title}"
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            resp = await client.get(url)
        if resp.status_code == _HTTP_OK:
            summary_json = resp.json()
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
