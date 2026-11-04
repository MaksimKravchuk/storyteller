"""Restore a saved game with the current admin-panel settings."""

from __future__ import annotations

from typing import TYPE_CHECKING

from config import Config
from engine.factory import create_engine
from engine.game_engine import GameEngine
from engine.model_overrides import load_role_overrides
from engine.search_settings import load_search_override

if TYPE_CHECKING:
    from db.repository import GameRepository
    from knowledge.graph import KnowledgeGraph
    from models.game_state import GameState
    from timeline.event import GameEvent


async def restore_engine_with_admin_settings(
    repo: "GameRepository",
    cfg: Config,
    loaded: tuple[GameState, KnowledgeGraph, list[GameEvent]],
    language: str,
) -> GameEngine:
    """Restore an engine from saved state using the *current* admin overrides.

    Models are not persisted per game (ADR-0007), so every resume follows the admin panel.
    """
    engine = create_engine(
        cfg,
        language,
        await load_role_overrides(repo),
        search_override=await load_search_override(repo),
    )
    await engine.restore_session(*loaded)
    return engine
