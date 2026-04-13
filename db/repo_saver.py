"""State saving helpers for GameRepository."""

from __future__ import annotations

from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from db import tables as tbl
from db.converters import (
    event as conv_event,
    knowledge as conv_knowledge,
    location as conv_loc,
    npc as conv_npc,
    player as conv_player,
    scene as conv_scene,
    setting as conv_setting,
    world_state as conv_world_state,
)
from db import repo_saver_helpers as saver_helpers
from knowledge.graph import KnowledgeGraph
from models.game_state import GameState
from timeline.event import GameEvent


async def _save_setting_and_player(session: AsyncSession, game_state_id: str, game_state: GameState) -> None:
    """Upsert setting and player rows."""
    await saver_helpers.upsert_one_to_one(
        session,
        tbl.settings,
        conv_setting.setting_to_row(game_state.setting, game_state_id),
    )
    await saver_helpers.upsert_one_to_one(
        session,
        tbl.players,
        conv_player.player_to_row(game_state.player, game_state_id),
    )


async def _save_world_objects(session: AsyncSession, game_state_id: str, game_state: GameState) -> None:
    """Replace locations, NPCs, and scene rows."""
    loc_rows = [conv_loc.location_to_row(loc, game_state_id) for loc in game_state.locations.values()]
    await saver_helpers.replace_rows(session, tbl.locations, game_state_id, loc_rows)

    npc_rows = [conv_npc.npc_to_row(npc, game_state_id) for npc in game_state.npcs.values()]
    await saver_helpers.replace_rows(session, tbl.npcs, game_state_id, npc_rows)

    await _save_scenes(session, game_state_id, game_state)


async def _save_scenes(session: AsyncSession, game_state_id: str, game_state: GameState) -> None:
    """Preserve historical scenes and upsert the current one."""
    await session.execute(
        update(tbl.scenes)
        .where(tbl.scenes.c.game_state_id == game_state_id)
        .where(tbl.scenes.c.is_current.is_(True))
        .values(is_current=False),
    )
    if game_state.current_scene:
        row = conv_scene.scene_to_row(
            game_state.current_scene,
            game_state_id,
            is_current=True,
            scene_number=game_state.scene_number,
        )
        stmt = (
            pg_insert(tbl.scenes)
            .values(**row)
            .on_conflict_do_update(
                index_elements=["id"],
                set_=saver_helpers.updatable_fields(row),
            )
        )
        await session.execute(stmt)


async def _save_knowledge(session: AsyncSession, game_state_id: str, knowledge_graph: KnowledgeGraph) -> None:
    """Replace knowledge nodes and edges."""
    nodes = knowledge_graph.all_nodes()
    await saver_helpers.replace_rows(
        session,
        tbl.knowledge_nodes,
        game_state_id,
        [conv_knowledge.knowledge_node_to_row(node, game_state_id) for node in nodes],
    )
    await saver_helpers.replace_rows(
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
    event_rows = [conv_event.game_event_to_row(ev, game_state_id) for ev in events] if events else []
    await saver_helpers.replace_rows(session, tbl.game_events, game_state_id, event_rows)


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
        world_state_payload = conv_world_state.world_state_to_dict(game_state.world_state)
        stmt = (
            pg_insert(tbl.game_states)
            .values(
                id=game_state.uuid,
                session_id=session_id,
                turn_count=game_state.turn_count,
                round_number=game_state.round_number,
                scene_number=game_state.scene_number,
                game_clock=game_state.game_clock,
                game_time=game_state.game_time,
                conversation_log=game_state.conversation_log,
                scene_conversation_log=game_state.scene_conversation_log,
                pending_clarification=game_state.pending_clarification,
                world_state=world_state_payload,
            )
            .on_conflict_do_update(
                index_elements=["session_id"],
                set_={
                    "turn_count": game_state.turn_count,
                    "round_number": game_state.round_number,
                    "scene_number": game_state.scene_number,
                    "game_clock": game_state.game_clock,
                    "game_time": game_state.game_time,
                    "conversation_log": game_state.conversation_log,
                    "scene_conversation_log": game_state.scene_conversation_log,
                    "pending_clarification": game_state.pending_clarification,
                    "world_state": world_state_payload,
                },
            )
            .returning(tbl.game_states.c.id)
        )
        upsert_result = await self._session.execute(stmt)
        game_state_id = upsert_result.scalar_one()
        await self._session.flush()

        await _persist_children(self._session, game_state_id, game_state, knowledge_graph, events)
