"""Wikipedia-backed :class:`BaseSearchClient` — the zero-config default."""

from __future__ import annotations

from research.base_search_client import BaseSearchClient, SearchResult
from research.wikipedia_client import WikipediaClient

_WIKI_URL = "https://en.wikipedia.org/wiki/{0}"


class WikipediaSearchClient(BaseSearchClient):
    """Adapts the existing :class:`WikipediaClient` to the search interface.

    ``search`` looks the query up as an article title and returns a single
    result whose ``snippet`` is the article extract — the encyclopedic
    summary the Data Miner has always grounded settings in. The wrapped
    client is exposed as :attr:`wikipedia` so the Data Miner keeps its
    extract-based fact lookups on the default backend, and so existing
    callers that injected a ``WikipediaClient`` keep working unchanged.
    """

    def __init__(self, wikipedia_client: WikipediaClient | None = None) -> None:
        self.wikipedia = wikipedia_client or WikipediaClient()

    async def search(self, query: str, *, max_results: int = 5) -> list[SearchResult]:
        """Return the Wikipedia summary for ``query`` as a single result.

        Yields an empty list when the article has no extract (e.g. a 404
        fallback), so the Data Miner treats it as a soft miss exactly as
        it did with the raw summary dict.
        """
        summary = await self.wikipedia.get_summary(query)
        extract = summary.get("extract", "")
        if not extract:
            return []
        title = summary.get("title", query)
        page_url = _WIKI_URL.format(title.replace(" ", "_"))
        return [SearchResult(title=title, url=page_url, snippet=extract)]
