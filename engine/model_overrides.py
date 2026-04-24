"""Bridge between persisted admin model overrides and engine construction.

The admin panel stores per-role model overrides in the ``admin_settings``
DB table. This module reads them and produces ``ModelConfig`` objects
keyed by role, for callers that build a new :class:`GameEngine`.
Restored games do not consult these overrides — they keep whatever
models they started with.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from defaults.models import ModelConfig

if TYPE_CHECKING:
    from config import Config
    from db.repository import GameRepository


async def load_role_overrides(
    repo: "GameRepository",
    cfg: "Config",
) -> dict[str, ModelConfig]:
    """Read DB role overrides and wrap them into ``ModelConfig`` objects.

    Returns a dict keyed by role (``director``/``agent``/``narrator``/
    ``dramaturge``); missing rows mean no override (caller falls back to
    ``cfg.<role>_model``). ``temperature`` and ``max_tokens`` come from
    ``Config`` since the override table only stores provider + model_id.
    """
    stored = await repo.settings.get_model_overrides()
    return {
        role: ModelConfig(
            provider=provider,
            model_id=model_id,
            temperature=cfg.temperature,
            max_tokens=cfg.max_tokens,
        )
        for role, (provider, model_id) in stored.items()
    }
