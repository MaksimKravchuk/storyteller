"""Constructor-time helpers for :class:`cast.data_miner.DataMiner`.

The Data Miner pulls in a prompt bundle and the default search client on
construction; both imports are pinned here so :mod:`cast.data_miner` stays inside the WPS201 import budget.
"""

from __future__ import annotations

from typing import Any

from prompts.data_miner_prompts import get_data_miner_prompts
from research.wikipedia_search_client import WikipediaSearchClient


def resolve_prompts(language: str) -> Any:
    """Return the language-localised prompt bundle for the Data Miner."""
    return get_data_miner_prompts(language)


def default_search_client() -> WikipediaSearchClient:
    """Return the Wikipedia-backed search client used when none is injected."""
    return WikipediaSearchClient()
