"""Constructor-time helpers for :class:`cast.data_miner.DataMiner`.

The Data Miner pulls in a Wikipedia client and a prompt bundle on
construction; both imports are pinned here so :mod:`cast.data_miner`
itself stays inside the WPS201 module-import budget after the KER-44
``UUID`` annotation was added.
"""

from __future__ import annotations

from typing import Any

from prompts.data_miner_prompts import get_data_miner_prompts
from research.wikipedia_client import WikipediaClient


def resolve_prompts(language: str) -> Any:
    """Return the language-localised prompt bundle for the Data Miner."""
    return get_data_miner_prompts(language)


def resolve_wikipedia_client(client: WikipediaClient | None) -> WikipediaClient:
    """Return ``client`` or a fresh :class:`WikipediaClient` when ``None``."""
    return client or WikipediaClient()
