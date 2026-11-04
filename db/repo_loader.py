"""State loading helpers for GameRepository."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db import tables as tbl
from db import repo_loader_helpers as helpers
from db.converters import event as conv_event, location as conv_loc, npc as conv_npc
from db.converters import player as conv_player, scene as conv_scene
from knowledge.graph import KnowledgeGraph
from timeline.event import GameEvent

if TYPE_CHECKING:
    from models.game_state import GameState


async def _load_player(session: AsyncSession, game_state_id: str, game_state: GameState) -> None:
    stmt = select(tbl.players).where(tbl.players.c.game_state_id == game_state_id)
    row = (await session.execute(stmt)).mappings().first()
    if row:
        game_state.player = conv_player.row_to_player(dict(row))


async def _load_locations(session: AsyncSession, game_state_id: str, game_state: GameState) -> None:
    stmt = select(tbl.locations).where(tbl.locations.c.game_state_id == game_state_id)
    for row in (await session.execute(stmt)).mappings():
        loc = conv_loc.row_to_location(dict(row))
        game_state.locations[loc.uuid] = loc


async def _load_npcs(session: AsyncSession, game_state_id: str, game_state: GameState) -> None:
    stmt = select(tbl.npcs).where(tbl.npcs.c.game_state_id == game_state_id)
    for row in (await session.execute(stmt)).mappings():
        npc = conv_npc.row_to_npc(dict(row))
        game_state.npcs[npc.uuid] = npc


async def _load_scene_and_events(
    session: AsyncSession,
    game_state_id: str,
    game_state: GameState,
) -> list[GameEvent]:
    """Load current scene into game_state and return events list."""
    scene_query = await session.execute(
        select(tbl.scenes).where(
            tbl.scenes.c.game_state_id == game_state_id,
            tbl.scenes.c.is_current.is_(True),
        ),
    )
    scene_row = scene_query.mappings().first()
    if scene_row:
        game_state.current_scene = conv_scene.row_to_scene(dict(scene_row))

    events_query = await session.execute(
        select(tbl.game_events).where(tbl.game_events.c.game_state_id == game_state_id),
    )
    return [conv_event.row_to_game_event(dict(event_row)) for event_row in events_query.mappings()]


async def _load_entities_and_scene(
    session: AsyncSession,
    game_state_id: str,
    game_state: GameState,
) -> list[GameEvent]:
    """Load player, locations, NPCs, scene, and events into game_state."""
    await _load_player(session, game_state_id, game_state)
    await _load_locations(session, game_state_id, game_state)
    await _load_npcs(session, game_state_id, game_state)
    return await _load_scene_and_events(session, game_state_id, game_state)


class StateLoader:
    """Loads full game state from the database."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def load(self, session_id: str) -> tuple[GameState, KnowledgeGraph, list[GameEvent]] | None:
        """Load full game state from PG. Returns None if no game exists."""
        base = await helpers.load_gs_and_setting(self._session, session_id)
        if base is None:
            return None
        gs_row, setting = base

        kg = await helpers.load_knowledge_graph(self._session, gs_row[helpers._COL_ID])
        game_state = helpers.hydrate_game_state(gs_row, setting, kg)
        return game_state, kg, await _load_entities_and_scene(self._session, gs_row[helpers._COL_ID], game_state)
