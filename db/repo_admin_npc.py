"""NPC-detail admin query: NPC row + knowledge subgraph rooted at the NPC."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import repo_admin_helpers as helpers
from db import tables as tbl


async def _fetch_npc_row(session: AsyncSession, session_id: str, npc_id: str) -> dict | None:
    """Return the NPC row joined to its owning session, or ``None`` when absent."""
    stmt = (
        select(tbl.npcs)
        .join(tbl.game_states, tbl.game_states.c.id == tbl.npcs.c.game_state_id)
        .where(tbl.game_states.c.session_id == session_id)
        .where(tbl.npcs.c.id == npc_id)
    )
    raw = (await session.execute(stmt)).mappings().first()
    return helpers._row_dict(raw) if raw else None


async def _fetch_edges_from(session: AsyncSession, game_state_id: str, npc_id: str) -> list[dict]:
    """Return edges rooted at ``npc_id`` within ``game_state_id``."""
    ke_cols = tbl.knowledge_edges.c
    stmt = select(tbl.knowledge_edges).where(ke_cols.game_state_id == game_state_id)
    stmt = stmt.where(ke_cols.from_node_id == npc_id)
    rows = await session.execute(stmt)
    return list(map(helpers._row_dict, rows.mappings()))


async def _fetch_nodes_by_ids(
    session: AsyncSession,
    game_state_id: str,
    node_ids: set[str],
) -> list[dict]:
    """Return knowledge nodes in ``game_state_id`` whose ids appear in ``node_ids``."""
    kn_cols = tbl.knowledge_nodes.c
    stmt = select(tbl.knowledge_nodes).where(kn_cols.game_state_id == game_state_id)
    stmt = stmt.where(kn_cols.id.in_(node_ids))
    rows = await session.execute(stmt)
    return list(map(helpers._row_dict, rows.mappings()))


async def _fetch_memory_subgraph(
    session: AsyncSession,
    game_state_id: str,
    npc_id: str,
) -> tuple[list[dict], list[dict]]:
    """Return ``(nodes, edges)`` of the knowledge subgraph rooted at ``npc_id``.

    ``npcs`` UUIDs double as the ``from_node_id`` in ``knowledge_edges`` because
    :func:`knowledge.graph.register_actor_node` registers NPCs by their UUID.
    """
    edges = await _fetch_edges_from(session, game_state_id, npc_id)
    if not edges:
        return ([], [])
    target_ids = {edge["to_node_id"] for edge in edges}
    nodes = await _fetch_nodes_by_ids(session, game_state_id, target_ids)
    return (nodes, edges)


async def fetch_npc_detail(session: AsyncSession, session_id: str, npc_id: str) -> dict | None:
    """Return an NPC detail payload (row + memory nodes + edges) or ``None``."""
    npc_row = await _fetch_npc_row(session, session_id, npc_id)
    if npc_row is None:
        return None
    nodes, edges = await _fetch_memory_subgraph(session, npc_row["game_state_id"], npc_id)
    return {"npc": npc_row, "memory_nodes": nodes, "memory_edges": edges}
