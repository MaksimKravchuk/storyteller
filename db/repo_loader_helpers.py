"""Helper functions for loading game state from the database."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import tables as tbl
from db.converters import knowledge as conv_knowledge, setting as conv_setting
from db.converters import world_state as conv_world_state
from knowledge.graph import KnowledgeGraph
from knowledge.node import EdgeType
from models.game_state import GameState
from models.scene_action_log import SceneActionEntry

_COL_ID = "id"


def _row_dict(row) -> dict:  # type: ignore[no-untyped-def]
    """Convert a SQLAlchemy mapping row to a plain dict."""
    return dict(row)


def _hydrate_scene_action_log(raw_entries: list[dict] | None) -> list[SceneActionEntry]:
    """Rebuild :class:`SceneActionEntry` objects from a JSONB column.

    The DB column has ``server_default='[]'`` so the value should be a
    list, but a NULL coming back from a pre-migration row is normalised
    to an empty list here.
    """
    if not raw_entries:
        return []
    return [SceneActionEntry(**raw) for raw in raw_entries]


def hydrate_game_state(gs_row: dict, setting: Any, kg: KnowledgeGraph) -> GameState:
    """Build a GameState from a DB row, setting, and knowledge graph."""
    game_state = GameState(setting=setting, knowledge_graph=kg)
    game_state.uuid = gs_row[_COL_ID]
    game_state.turn_count = gs_row["turn_count"]
    game_state.round_number = gs_row.get("round_number", 0)
    game_state.scene_number = gs_row.get("scene_number", 0)
    game_state.game_clock = gs_row["game_clock"]
    game_state.game_time = gs_row["game_time"]
    game_state.conversation_log = gs_row["conversation_log"]
    game_state.scene_conversation_log = gs_row.get("scene_conversation_log", [])
    game_state.scene_action_log = _hydrate_scene_action_log(gs_row.get("scene_action_log"))
    game_state.pending_clarification = gs_row.get("pending_clarification")
    game_state.world_state = conv_world_state.dict_to_world_state(gs_row.get("world_state"))
    return game_state


async def load_gs_and_setting(session: AsyncSession, session_id: str) -> tuple[dict, Any] | None:
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
    return gs_row, conv_setting.row_to_setting(_row_dict(setting_row))


async def load_knowledge_graph(session: AsyncSession, game_state_id: str) -> KnowledgeGraph:
    """Load knowledge graph nodes and edges from the database."""
    kg = KnowledgeGraph()
    nodes_query = await session.execute(
        select(tbl.knowledge_nodes).where(tbl.knowledge_nodes.c.game_state_id == game_state_id),
    )
    for row in nodes_query.mappings():
        node = conv_knowledge.row_to_knowledge_node(_row_dict(row))
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
