"""Admin query helpers for GameRepository."""

from __future__ import annotations

from functools import partial
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import repo_admin_helpers as helpers
from db import repo_admin_npc
from db import repo_admin_users
from db import tables as tbl

_COL_ID = "id"


async def fetch_events(session: AsyncSession, session_id: str) -> list[dict]:
    """Get all events for a session."""
    return await helpers.joined_rows(
        session,
        tbl.game_events,
        session_id,
        tbl.game_events.c.scheduled_at,
    )


async def fetch_scenes(session: AsyncSession, session_id: str) -> list[dict]:
    """Get all scenes (including historical) for a session."""
    return await helpers.joined_rows(
        session,
        tbl.scenes,
        session_id,
        tbl.scenes.c.scene_number,
    )


async def fetch_knowledge_graph(session: AsyncSession, session_id: str) -> dict:
    """Get knowledge graph nodes and edges for a session."""
    gs_col = tbl.game_states.c
    gs_id_stmt = select(gs_col.id).where(gs_col.session_id == session_id)
    game_state_id = (await session.execute(gs_id_stmt)).scalar()
    if not game_state_id:
        return {"nodes": [], "edges": []}
    nodes = await helpers.joined_rows_by_gs(session, tbl.knowledge_nodes, game_state_id)
    edges = await helpers.joined_rows_by_gs(session, tbl.knowledge_edges, game_state_id)
    return {"nodes": nodes, "edges": edges}


class AdminQueries:
    """Read-only admin queries against the game database."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        # Bind the knowledge-graph fetcher as an attribute so its logic
        # lives as a module-level function (usable without a class
        # instance from tests & helpers) while admin code can still
        # ``await repo.admin.get_knowledge_graph(sid)``.
        self.get_knowledge_graph = partial(fetch_knowledge_graph, session)
        self.list_users = partial(repo_admin_users.list_users, session)
        self.get_user_detail = partial(repo_admin_users.get_user_detail, session)

    async def list_sessions(
        self,
        limit: int = 50,
        offset: int = 0,
        *,
        web_player_id: str | None = None,
        telegram_chat_id: int | None = None,
        search: str | None = None,
    ) -> list[dict]:
        """List sessions with basic game info, optionally filtered by player identity."""
        stmt = (
            select(
                tbl.sessions.c.id,
                tbl.sessions.c.telegram_chat_id,
                tbl.sessions.c.web_player_id,
                tbl.sessions.c.state,
                tbl.sessions.c.language,
                tbl.sessions.c.created_at,
                tbl.sessions.c.updated_at,
                tbl.game_states.c.turn_count,
                tbl.game_states.c.game_clock,
                tbl.game_states.c.game_time,
                tbl.accounts.c.id.label("account_id"),
                tbl.accounts.c.email.label("account_email"),
            )
            .outerjoin(tbl.game_states, tbl.game_states.c.session_id == tbl.sessions.c.id)
            .outerjoin(tbl.accounts, tbl.accounts.c.id == tbl.sessions.c.web_player_id)
            .order_by(tbl.sessions.c.updated_at.desc(), tbl.sessions.c.id.desc())
            .limit(limit)
            .offset(offset)
        )
        if web_player_id is not None:
            stmt = stmt.where(tbl.sessions.c.web_player_id == web_player_id)
        if telegram_chat_id is not None:
            stmt = stmt.where(tbl.sessions.c.telegram_chat_id == telegram_chat_id)
        if search:
            stmt = repo_admin_users.apply_search_filter(stmt, search)
        sessions_query = await self.session.execute(stmt)
        return list(map(helpers._row_dict, sessions_query.mappings()))

    async def get_session_detail(self, session_id: str) -> dict | None:
        """Get full session detail for admin view."""
        stmt = (
            select(
                tbl.sessions.c.id,
                tbl.sessions.c.telegram_chat_id,
                tbl.sessions.c.web_player_id,
                tbl.sessions.c.state,
                tbl.sessions.c.language,
                tbl.sessions.c.title,
                tbl.sessions.c.archived_at,
                tbl.sessions.c.created_at,
                tbl.sessions.c.updated_at,
                tbl.accounts.c.id.label("account_id"),
                tbl.accounts.c.email.label("account_email"),
            )
            .outerjoin(tbl.accounts, tbl.accounts.c.id == tbl.sessions.c.web_player_id)
            .where(tbl.sessions.c.id == session_id)
        )
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

    async def get_npc_detail(self, session_id: str, npc_id: str) -> dict | None:
        """Return one NPC's row plus its memory graph subset, or ``None``."""
        return await repo_admin_npc.fetch_npc_detail(self.session, session_id, npc_id)
