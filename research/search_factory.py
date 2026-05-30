"""Factory mapping a provider name to a concrete :class:`BaseSearchClient`.

Mirrors :func:`llm.factory.create_llm_client`: a provider string selects the
implementation and an unknown provider raises ``ValueError``. Wikipedia is the
zero-config default used when nothing else is configured.
"""

from __future__ import annotations

from research.base_search_client import BaseSearchClient
from research.searxng_search_client import SearXNGSearchClient
from research.tavily_search_client import TavilySearchClient
from research.wikipedia_search_client import WikipediaSearchClient

PROVIDER_WIKIPEDIA = "wikipedia"
PROVIDER_TAVILY = "tavily"
PROVIDER_SEARXNG = "searxng"


def create_search_client(
    provider: str,
    *,
    tavily_api_key: str | None = None,
    searxng_base_url: str | None = None,
) -> BaseSearchClient:
    """Create the search client for ``provider``.

    ``wikipedia`` (the default) needs no configuration. ``tavily`` requires
    ``tavily_api_key`` and ``searxng`` requires ``searxng_base_url``; a missing
    value raises ``ValueError`` at construction rather than silently falling
    back to Wikipedia. An unknown provider also raises ``ValueError``.
    """
    if provider == PROVIDER_WIKIPEDIA:
        return WikipediaSearchClient()
    if provider == PROVIDER_TAVILY:
        return TavilySearchClient(tavily_api_key)
    if provider == PROVIDER_SEARXNG:
        return SearXNGSearchClient(searxng_base_url)
    raise ValueError(f"Unknown search provider: {provider}")
