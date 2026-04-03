"""GameRepository — single persistence layer for all game data."""

from __future__ import annotations

import uuid as _uuid
from typing import Any

import sqlalchemy
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from db import tables as tbl, repo_admin, repo_ai_logs, repo_loader, repo_saver
from knowledge import graph as graph_mod
from models.game_state import GameState
from timeline.event import GameEvent


def _row_dict(row) -> dict:  # type: ignore[no-untyped-def]
    """Convert a SQLAlchemy mapping row to a plain dict."""
    return dict(row)


class GameRepository:
    """Async repository facade — delegates to specialised helpers."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self.admin = repo_admin.AdminQueries(session)
        self._loader = repo_loader.StateLoader(session)
        self._saver = repo_saver.StateSaver(session)
        self.ai_logs = repo_ai_logs.AILogStore(session)

    async def get_or_create_session(self, telegram_chat_id: int) -> dict:
        """Return session row dict, creating one if it doesn't exist."""
        stmt = (
            pg_insert(tbl.sessions)
            .values(id=str(_uuid.uuid4()), telegram_chat_id=telegram_chat_id)
            .on_conflict_do_nothing(index_elements=["telegram_chat_id"])
        )
        await self._session.execute(stmt)

        query_result = await self._session.execute(
            sqlalchemy.select(tbl.sessions).where(tbl.sessions.c.telegram_chat_id == telegram_chat_id),
        )
        row = query_result.mappings().one()
        return _row_dict(row)

    async def update_session(
        self,
        session_id: str,
        *,
        state: str | None = None,
        language: str | None = None,
    ) -> None:
        """Update session fields (state and/or language)."""
        update_fields: dict[str, Any] = {}
        if state is not None:
            update_fields["state"] = state
        if language is not None:
            update_fields["language"] = language
        if update_fields:
            sessions_filter = tbl.sessions.c.id == session_id
            stmt = sqlalchemy.update(tbl.sessions).where(sessions_filter).values(**update_fields)
            await self._session.execute(stmt)

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

    async def save_ai_call_logs(
        self,
        logs: list[dict[str, Any]],
        turn_number: int | None = None,
    ) -> None:
        """Batch insert AI call log entries."""
        await self.ai_logs.save(logs, turn_number=turn_number)

    async def get_ai_call_logs(
        self,
        session_id: str,
        turn_number: int | None = None,
        limit: int = 200,
    ) -> list[dict]:
        """Get AI call logs for a session."""
        return await self.ai_logs.get(session_id, turn_number=turn_number, limit=limit)
