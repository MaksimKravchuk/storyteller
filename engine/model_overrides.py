"""Bridge between persisted admin model overrides and engine construction.

The admin panel stores per-role model overrides in the ``admin_settings``
DB table. This module reads them and produces ``ModelConfig`` objects
keyed by role, for callers that build a new :class:`GameEngine`.
Restored games consult them too, so they follow the current admin choice.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from defaults.models import ModelConfig

if TYPE_CHECKING:
    from db.repository import GameRepository


async def load_role_overrides(
    repo: "GameRepository",
) -> dict[str, ModelConfig]:
    """Read DB role overrides and wrap them into ``ModelConfig`` objects.

    Returns a dict keyed by role (``director``/``agent``/``narrator``/
    ``dramaturge``); missing rows mean no override (caller falls back to
    ``cfg.<role>_model``). Temperature and max_tokens use ``ModelConfig`` defaults.
    """
    stored = await repo.settings.get_model_overrides()
    overrides: dict[str, ModelConfig] = {}
    for role, (provider, model_id) in stored.items():
        overrides[role] = ModelConfig(provider=provider, model_id=model_id)
    return overrides
