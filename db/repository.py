"""GameRepository — single persistence layer for all game data."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from db import (
    repo_admin,
    repo_ai_logs,
    repo_loader,
    repo_saver,
    repo_sessions,
    repo_settings,
    repo_turn_events,
)
from knowledge import graph as graph_mod
from models.game_state import GameState
from timeline.event import GameEvent


class GameRepository:
    """Async repository facade — delegates to specialised helpers."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.admin = repo_admin.AdminQueries(session)
        self._loader = repo_loader.StateLoader(session)
        self._saver = repo_saver.StateSaver(session)
        self.ai_logs = repo_ai_logs.AILogStore(session)
        self.turn_events = repo_turn_events.TurnEventStore(session)
        self.sessions = repo_sessions.SessionStore(session)
        self.settings = repo_settings.AdminSettingsStore(session)

    async def rollback(self) -> None:
        """Roll back the current transaction (use after a failed op to reuse the session)."""
        await self._session.rollback()

    async def commit(self) -> None:
        """Commit the current transaction before returning a player-visible response."""
        await self._session.commit()

    async def load_game_state(
        self,
        session_id: str,
    ) -> tuple[GameState, graph_mod.KnowledgeGraph, list[GameEvent]] | None:
        """Load full game state. Returns None if no game exists for this session."""
        return await self._loader.load(session_id)

    async def save_game_state(
        self,
        session_id: str,
        game_state: GameState,
        knowledge_graph: graph_mod.KnowledgeGraph,
        events: list[GameEvent],
    ) -> None:
        """Persist full game state to PG."""
        await self._saver.save(session_id, game_state, knowledge_graph, events)
