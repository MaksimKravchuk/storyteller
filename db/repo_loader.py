"""State loading helpers for GameRepository."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import tables as tbl
from db.converters import (
    row_to_game_event,
    row_to_knowledge_node,
    row_to_location,
    row_to_npc,
    row_to_player,
    row_to_scene,
    row_to_setting,
)
from knowledge.graph import KnowledgeGraph
from knowledge.node import EdgeType
from models.game_state import GameState
from timeline.event import GameEvent

_COL_ID = "id"


def _row_dict(row) -> dict:  # type: ignore[no-untyped-def]
    """Convert a SQLAlchemy mapping row to a plain dict."""
    return dict(row)


def _hydrate_game_state(gs_row: dict, setting: Any, kg: KnowledgeGraph) -> GameState:
    """Build a GameState from a DB row, setting, and knowledge graph."""
    game_state = GameState(setting=setting, knowledge_graph=kg)
    game_state.uuid = gs_row[_COL_ID]
    game_state.turn_count = gs_row["turn_count"]
    game_state.scene_number = gs_row.get("scene_number", 0)
    game_state.game_clock = gs_row["game_clock"]
    game_state.game_time = gs_row["game_time"]
    game_state.conversation_log = gs_row["conversation_log"]
    game_state.scene_conversation_log = gs_row.get("scene_conversation_log", [])
    game_state.pending_clarification = gs_row.get("pending_clarification")
    return game_state


async def _load_gs_and_setting(session: AsyncSession, session_id: str) -> tuple[dict, Any] | None:
    """Load game_states row and setting, or return None."""
    gs_query = await session.execute(
        select(tbl.game_states).where(tbl.game_states.c.session_id == session_id),
    )
    gs_mapping = gs_query.mappings().first()
    if gs_mapping is None:
        return None
    gs_row = _row_dict(gs_mapping)

    setting_query = await session.execute(
        select(tbl.settings).where(tbl.settings.c.game_state_id == gs_row[_COL_ID]),
    )
    setting_row = setting_query.mappings().first()
    if setting_row is None:
        return None
    return gs_row, row_to_setting(_row_dict(setting_row))


async def _load_knowledge_graph(session: AsyncSession, game_state_id: str) -> KnowledgeGraph:
    """Load knowledge graph nodes and edges from the database."""
    kg = KnowledgeGraph()
    nodes_query = await session.execute(
        select(tbl.knowledge_nodes).where(tbl.knowledge_nodes.c.game_state_id == game_state_id),
    )
    for row in nodes_query.mappings():
        node = row_to_knowledge_node(_row_dict(row))
        kg.add_node(node)

    edges_query = await session.execute(
        select(tbl.knowledge_edges).where(tbl.knowledge_edges.c.game_state_id == game_state_id),
    )
    for row in edges_query.mappings():
        kg.add_edge(
            row["from_node_id"],
            row["to_node_id"],
            EdgeType(row["edge_type"]),
            row["metadata_"] if row["metadata_"] else None,
        )
    return kg


async def _load_player(session: AsyncSession, game_state_id: str, game_state: GameState) -> None:
    stmt = select(tbl.players).where(tbl.players.c.game_state_id == game_state_id)
    row = (await session.execute(stmt)).mappings().first()
    if row:
        game_state.player = row_to_player(_row_dict(row))


async def _load_locations(session: AsyncSession, game_state_id: str, game_state: GameState) -> None:
    stmt = select(tbl.locations).where(tbl.locations.c.game_state_id == game_state_id)
    for row in (await session.execute(stmt)).mappings():
        loc = row_to_location(_row_dict(row))
        game_state.locations[loc.uuid] = loc


async def _load_npcs(session: AsyncSession, game_state_id: str, game_state: GameState) -> None:
    stmt = select(tbl.npcs).where(tbl.npcs.c.game_state_id == game_state_id)
    for row in (await session.execute(stmt)).mappings():
        npc = row_to_npc(_row_dict(row))
        game_state.npcs[npc.uuid] = npc


async def _load_entities(session: AsyncSession, game_state_id: str, game_state: GameState) -> None:
    """Load player, locations, and NPCs into game_state."""
    await _load_player(session, game_state_id, game_state)
    await _load_locations(session, game_state_id, game_state)
    await _load_npcs(session, game_state_id, game_state)


async def _load_scene_and_events(
    session: AsyncSession,
    game_state_id: str,
    game_state: GameState,
) -> list[GameEvent]:
    """Load current scene into game_state and return events list."""
    scene_query = await session.execute(
        select(tbl.scenes).where(
            tbl.scenes.c.game_state_id == game_state_id,
            tbl.scenes.c.is_current == True,  # noqa: E712
        ),
    )
    scene_row = scene_query.mappings().first()
    if scene_row:
        game_state.current_scene = row_to_scene(_row_dict(scene_row))

    events_query = await session.execute(
        select(tbl.game_events).where(tbl.game_events.c.game_state_id == game_state_id),
    )
    return [row_to_game_event(_row_dict(event_row)) for event_row in events_query.mappings()]


class StateLoader:
    """Loads full game state from the database."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def load(self, session_id: str) -> tuple[GameState, KnowledgeGraph, list[GameEvent]] | None:
        """Load full game state from PG. Returns None if no game exists."""
        base = await _load_gs_and_setting(self._session, session_id)
        if base is None:
            return None
        gs_row, setting = base

        kg = await _load_knowledge_graph(self._session, gs_row[_COL_ID])
        game_state = _hydrate_game_state(gs_row, setting, kg)
        await _load_entities(self._session, gs_row[_COL_ID], game_state)
        return game_state, kg, await _load_scene_and_events(self._session, gs_row[_COL_ID], game_state)
