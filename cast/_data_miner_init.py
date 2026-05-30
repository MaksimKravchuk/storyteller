"""Constructor-time helpers for :class:`cast.data_miner.DataMiner`.

The Data Miner pulls in a prompt bundle and a search client on
construction; both imports are pinned here so :mod:`cast.data_miner`
itself stays inside the WPS201 module-import budget.
"""

from __future__ import annotations

from typing import Any

from prompts.data_miner_prompts import get_data_miner_prompts
from research.base_search_client import BaseSearchClient
from research.wikipedia_client import WikipediaClient
from research.wikipedia_search_client import WikipediaSearchClient


def resolve_prompts(language: str) -> Any:
    """Return the language-localised prompt bundle for the Data Miner."""
    return get_data_miner_prompts(language)


def resolve_search_client(
    search_client: BaseSearchClient | None,
    wikipedia_client: WikipediaClient | None,
) -> BaseSearchClient:
    """Return the search client the Data Miner should research through.

    An explicit ``search_client`` wins — this is how non-Wikipedia providers
    (Tavily, SearXNG) are injected. Otherwise we fall back to a Wikipedia-backed
    client, wrapping an injected ``wikipedia_client`` when one is supplied (the
    legacy injection seam used by tests) or building a default one.
    """
    if search_client is not None:
        return search_client
    return WikipediaSearchClient(wikipedia_client)
