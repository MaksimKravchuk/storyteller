"""State saving helpers for GameRepository."""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from db import tables as tbl
from db.converters import (
    game_event_to_row,
    knowledge_node_to_row,
    location_to_row,
    npc_to_row,
    player_to_row,
    scene_to_row,
    setting_to_row,
)
from knowledge.graph import KnowledgeGraph
from models.game_state import GameState
from timeline.event import GameEvent

_COL_ID = "id"
_COL_GAME_STATE_ID = "game_state_id"


def _updatable_fields(row: dict) -> dict:
    """Return row fields excluding primary/foreign key columns."""
    skip = {_COL_ID, _COL_GAME_STATE_ID}
    return {key: col_val for key, col_val in row.items() if key not in skip}


async def _replace_rows(session: AsyncSession, table: Any, game_state_id: str, rows: list) -> None:
    """Delete all rows for game_state_id, then bulk-insert replacements."""
    del_stmt = delete(table).where(table.c.game_state_id == game_state_id)
    await session.execute(del_stmt)
    if rows:
        await session.execute(table.insert(), rows)


async def _upsert_one_to_one(session: AsyncSession, table: Any, row: dict) -> None:
    """Upsert a single row keyed by game_state_id."""
    stmt = (
        pg_insert(table)
        .values(**row)
        .on_conflict_do_update(
            index_elements=[_COL_GAME_STATE_ID],
            set_=_updatable_fields(row),
        )
    )
    await session.execute(stmt)


async def _save_setting_and_player(session: AsyncSession, game_state_id: str, game_state: GameState) -> None:
    """Upsert setting and player rows."""
    await _upsert_one_to_one(session, tbl.settings, setting_to_row(game_state.setting, game_state_id))
    await _upsert_one_to_one(session, tbl.players, player_to_row(game_state.player, game_state_id))


async def _save_world_objects(session: AsyncSession, game_state_id: str, game_state: GameState) -> None:
    """Replace locations, NPCs, and scene rows."""
    loc_rows = [location_to_row(loc, game_state_id) for loc in game_state.locations.values()]
    await _replace_rows(session, tbl.locations, game_state_id, loc_rows)

    npc_rows = [npc_to_row(npc, game_state_id) for npc in game_state.npcs.values()]
    await _replace_rows(session, tbl.npcs, game_state_id, npc_rows)

    scene_rows = (
        [scene_to_row(game_state.current_scene, game_state_id, is_current=True)] if game_state.current_scene else []
    )
    await _replace_rows(session, tbl.scenes, game_state_id, scene_rows)


async def _save_knowledge(session: AsyncSession, game_state_id: str, knowledge_graph: KnowledgeGraph) -> None:
    """Replace knowledge nodes and edges."""
    nodes = knowledge_graph.all_nodes()
    await _replace_rows(
        session,
        tbl.knowledge_nodes,
        game_state_id,
        [knowledge_node_to_row(node, game_state_id) for node in nodes],
    )
    await _replace_rows(
        session,
        tbl.knowledge_edges,
        game_state_id,
        [
            {
                "game_state_id": game_state_id,
                "from_node_id": node.uuid,
                "to_node_id": target_id,
                "edge_type": edge_type.value,
                "metadata_": {},
            }
            for node in nodes
            for target_id, edge_type in knowledge_graph.get_edges_from(node.uuid)
        ],
    )


async def _persist_children(
    session: AsyncSession,
    game_state_id: str,
    game_state: GameState,
    knowledge_graph: KnowledgeGraph,
    events: list[GameEvent],
) -> None:
    """Persist all child tables for a game state."""
    await _save_setting_and_player(session, game_state_id, game_state)
    await _save_world_objects(session, game_state_id, game_state)
    await _save_knowledge(session, game_state_id, knowledge_graph)
    event_rows = [game_event_to_row(ev, game_state_id) for ev in events] if events else []
    await _replace_rows(session, tbl.game_events, game_state_id, event_rows)


class StateSaver:
    """Persists full game state to the database."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(
        self,
        session_id: str,
        game_state: GameState,
        knowledge_graph: KnowledgeGraph,
        events: list[GameEvent],
    ) -> None:
        """Persist full game state to PG (upsert game_states, delete+insert children)."""
        stmt = (
            pg_insert(tbl.game_states)
            .values(
                id=game_state.uuid,
                session_id=session_id,
                turn_count=game_state.turn_count,
                scene_number=game_state.scene_number,
                game_clock=game_state.game_clock,
                game_time=game_state.game_time,
                conversation_log=game_state.conversation_log,
                scene_conversation_log=game_state.scene_conversation_log,
                pending_clarification=game_state.pending_clarification,
            )
            .on_conflict_do_update(
                index_elements=["session_id"],
                set_={
                    "turn_count": game_state.turn_count,
                    "scene_number": game_state.scene_number,
                    "game_clock": game_state.game_clock,
                    "game_time": game_state.game_time,
                    "conversation_log": game_state.conversation_log,
                    "scene_conversation_log": game_state.scene_conversation_log,
                    "pending_clarification": game_state.pending_clarification,
                },
            )
            .returning(tbl.game_states.c.id)
        )
        upsert_result = await self._session.execute(stmt)
        game_state_id = upsert_result.scalar_one()
        await self._session.flush()

        await _persist_children(self._session, game_state_id, game_state, knowledge_graph, events)
