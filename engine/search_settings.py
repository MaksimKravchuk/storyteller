"""Bridge between persisted admin search settings and engine construction.

Mirrors :mod:`engine.model_overrides`: the admin panel stores the operator's
chosen search provider (and its credentials) in ``admin_settings``; this module
reads them into a :class:`SearchSettings` that a new :class:`GameEngine` build
uses to override the env-derived defaults. Restored games consult them too, so they follow the current admin choice.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from db.repository import GameRepository


@dataclass(frozen=True)
class SearchSettings:
    """Operator-chosen search provider + credentials (any field may be unset)."""

    provider: str | None = None
    tavily_api_key: str | None = None
    searxng_base_url: str | None = None


async def load_search_override(repo: "GameRepository") -> SearchSettings:
    """Read DB search settings into a :class:`SearchSettings`.

    Missing rows leave fields ``None``; the engine factory then falls back to
    the ``cfg.search_*`` env defaults for whatever is unset.
    """
    stored = await repo.settings.search_overrides()
    return SearchSettings(
        provider=stored.get("provider"),
        tavily_api_key=stored.get("tavily_api_key"),
        searxng_base_url=stored.get("searxng_base_url"),
    )
