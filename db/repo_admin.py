"""Admin query helpers for GameRepository."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import tables as tbl
from db import repo_admin_helpers as helpers

_COL_ID = "id"


async def fetch_events(session: AsyncSession, session_id: str) -> list[dict]:
    """Get all events for a session."""
    return await helpers.joined_rows(
        session,
        tbl.game_events,
        session_id,
        tbl.game_events.c.scheduled_at,
    )


class AdminQueries:
    """Read-only admin queries against the game database."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_sessions(self, limit: int = 50, offset: int = 0) -> list[dict]:
        """List sessions with basic game info for admin view."""
        stmt = (
            select(
                tbl.sessions.c.id,
                tbl.sessions.c.telegram_chat_id,
                tbl.sessions.c.state,
                tbl.sessions.c.language,
                tbl.sessions.c.created_at,
                tbl.sessions.c.updated_at,
                tbl.game_states.c.turn_count,
                tbl.game_states.c.game_clock,
                tbl.game_states.c.game_time,
            )
            .outerjoin(tbl.game_states, tbl.game_states.c.session_id == tbl.sessions.c.id)
            .order_by(tbl.sessions.c.updated_at.desc())
            .limit(limit)
            .offset(offset)
        )
        sessions_query = await self.session.execute(stmt)
        return list(map(helpers._row_dict, sessions_query.mappings()))

    async def get_session_detail(self, session_id: str) -> dict | None:
        """Get full session detail for admin view."""
        stmt = select(tbl.sessions).where(tbl.sessions.c.id == session_id)
        session_row = (await self.session.execute(stmt)).mappings().first()
        if not session_row:
            return None
        detail: dict[str, Any] = {"session": helpers._row_dict(session_row)}

        gs_stmt = select(tbl.game_states).where(tbl.game_states.c.session_id == session_id)
        gs_mapping = (await self.session.execute(gs_stmt)).mappings().first()
        if not gs_mapping:
            detail["game_state"] = None
            return detail

        detail["game_state"] = helpers._row_dict(gs_mapping)
        await helpers.populate_detail(self.session, detail, gs_mapping[_COL_ID])
        return detail

    async def get_conversation_log(self, session_id: str) -> list[dict]:
        """Get conversation log for a session."""
        log_query = await self.session.execute(
            select(tbl.game_states.c.conversation_log).where(tbl.game_states.c.session_id == session_id),
        )
        row = log_query.scalar()
        return row if row else []

    async def get_npcs(self, session_id: str) -> list[dict]:
        """Get all NPCs for a session."""
        return await helpers.joined_rows(self.session, tbl.npcs, session_id)

    async def get_locations(self, session_id: str) -> list[dict]:
        """Get all locations for a session."""
        return await helpers.joined_rows(self.session, tbl.locations, session_id)

    async def get_knowledge_graph(self, session_id: str) -> dict:
        """Get knowledge graph nodes and edges for a session."""
        gs_id_stmt = select(tbl.game_states.c.id).where(
            tbl.game_states.c.session_id == session_id,
        )
        game_state_id = (await self.session.execute(gs_id_stmt)).scalar()
        if not game_state_id:
            return {"nodes": [], "edges": []}

        nodes = await self.session.execute(
            select(tbl.knowledge_nodes).where(tbl.knowledge_nodes.c.game_state_id == game_state_id),
        )
        edges_stmt = select(tbl.knowledge_edges).where(
            tbl.knowledge_edges.c.game_state_id == game_state_id,
        )
        edges = await self.session.execute(edges_stmt)
        return {
            "nodes": list(map(helpers._row_dict, nodes.mappings())),
            "edges": list(map(helpers._row_dict, edges.mappings())),
        }
