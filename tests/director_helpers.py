"""Shared factory functions for Director tests."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

from cast.director import Director, DirectorCast, DirectorDeps
from knowledge.graph import KnowledgeGraph
from knowledge.memory import MemoryManager
from models.game_state import GameState
from models.npc_card import NPCCard
from models.scene import Scene, SceneNPC
from models.setting import Setting
from timeline.event_manager import EventManager


def make_setting() -> Setting:
    """Create a minimal Setting for tests."""
    return Setting(
        name="Ancient Rome",
        time_period="1st century AD",
        region="Italy",
        summary="The Roman Empire.",
    )


def make_game_state() -> GameState:
    """Create a GameState with a default scene containing one guard NPC."""
    kg = KnowledgeGraph()
    gs = GameState(setting=make_setting(), knowledge_graph=kg)
    gs.current_scene = Scene(
        location_id="forum",
        description="The bustling Roman Forum.",
        npcs_present=[SceneNPC(role="guard", uuid="npc-1")],
        points_of_interest=["fountain", "statue"],
    )
    return gs


def make_mock_agent(return_value: object = None) -> AsyncMock:
    """Create a mock agent with both .act and .execute wired."""
    mock = AsyncMock()
    mock.act = AsyncMock(return_value=return_value)
    mock.execute = AsyncMock(return_value=return_value)
    return mock


def make_cast(narrator_response: str = "Narrated result.") -> DirectorCast:
    """Build a DirectorCast with mocked agents."""
    return DirectorCast(
        scene_builder=make_mock_agent(
            Scene(
                location_id="new-loc",
                description="A new place.",
                npcs_present=[SceneNPC(role="merchant")],
            )
        ),
        narrator=make_mock_agent(narrator_response),
        npc_generator=make_mock_agent([]),
        data_miner=AsyncMock(),
    )


def make_director(
    game_state: GameState | None = None,
    route_response: dict | None = None,
    narrator_response: str = "Narrated result.",
) -> Director:
    """Create a Director with mocked LLM and agents."""
    gs = game_state or make_game_state()
    the_director = Director(
        llm_client=AsyncMock(),
        deps=DirectorDeps(
            game_state=gs,
            event_manager=EventManager(game_state=gs, knowledge_graph=gs.knowledge_graph),
            memory_manager=MagicMock(spec=MemoryManager),
        ),
        cast=make_cast(narrator_response),
        language="English",
    )
    if route_response:
        the_director._router._send_json = AsyncMock(return_value=route_response)  # type: ignore[method-assign]
    return the_director


def setup_npc(
    gs: GameState,
    uuid: str,
    name: str = "Guard",
    occupation: str = "city guard",
    **kwargs: Any,
) -> NPCCard:
    """Create an NPC, assign uuid and mood, register in game state."""
    mood = kwargs.pop("mood", "neutral")
    npc = NPCCard(name=name, occupation=occupation, **kwargs)
    npc.uuid = uuid
    npc.current_mood = mood
    gs.npcs[uuid] = npc
    return npc
