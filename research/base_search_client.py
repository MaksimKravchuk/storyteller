"""Provider-agnostic search abstraction for the Data Miner.

Mirrors the LLM provider pattern (``llm/base_client.py`` + ``llm/factory.py``):
a small typed result, an abstract async client, and a factory that maps a
provider name to a concrete implementation. The Data Miner researches a game
setting through this interface, so the backing search engine — Wikipedia,
Tavily, or a self-hosted SearXNG — is swappable via configuration without
touching the agent.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class SearchResult:
    """A single research hit returned by a :class:`BaseSearchClient`."""

    title: str
    url: str
    snippet: str


class BaseSearchClient(ABC):
    """Provider-agnostic research search interface.

    Concrete implementations live in ``wikipedia_search_client.py``,
    ``tavily_search_client.py`` and ``searxng_search_client.py``.
    """

    @abstractmethod
    async def search(self, query: str, *, max_results: int = 5) -> list[SearchResult]:
        """Return up to ``max_results`` results for ``query``.

        Implementations degrade to an empty list on a missing article,
        a non-success HTTP status, or zero hits — they do not raise for
        the "no results" case, so callers can treat an empty list as a
        soft miss.
        """
