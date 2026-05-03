"""Shared fixtures for ``test_npc_goal_resolution`` (state, stubs, helpers).

Extracted to keep the test module under the WPS201 import-count budget.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from knowledge.graph import KnowledgeGraph
from knowledge.memory import MemoryEventResult
from models.game_state import GameState, PlayerState
from models.location import Location
from models.npc_card import NPCCard
from models.scene import Scene, SceneNPC
from models.setting import Setting
from models.world_state import WorldThread
from tests._uuid_helpers import make_uuid

_ZERO_GAME_TIME = float(0)


@dataclass
class RecordingMemoryManager:
    """Captures :meth:`create_memory_from_event` calls for assertion."""

    calls: list[dict[str, Any]] = field(default_factory=list)

    async def create_memory_from_event(
        self,
        event_description: str,
        witness_ids: list[str],
        scope: Any,
        location_id: str | None = None,
        game_time: float = _ZERO_GAME_TIME,
    ) -> MemoryEventResult:
        self.calls.append(
            {
                "event_description": event_description,
                "witness_ids": witness_ids,
                "scope": scope,
                "location_id": location_id,
                "game_time": game_time,
            },
        )
        return MemoryEventResult(canonical_id=None, all_ids=())


def make_actor_target_state() -> tuple[GameState, NPCCard, NPCCard, Location]:
    """Build a minimal GameState with two co-located NPCs (``Brutus`` + ``Marcus``)."""
    location = Location(name="Taberna", description="", location_type="building")
    actor = NPCCard(name="Brutus", occupation="legionary")
    actor.uuid = make_uuid("npc-brutus")
    actor.location_id = location.uuid
    target = NPCCard(name="Marcus", occupation="merchant")
    target.uuid = make_uuid("npc-marcus")
    target.location_id = location.uuid
    state = GameState(
        setting=Setting(name="Test", time_period="now", region="lab", summary=""),
        knowledge_graph=KnowledgeGraph(),
        player=PlayerState(name="Player", location_id=location.uuid),
    )
    state.locations[location.uuid] = location
    state.npcs[actor.uuid] = actor
    state.npcs[target.uuid] = target
    state.current_scene = Scene(
        location_id=location.uuid,
        description="",
        npcs_present=[
            SceneNPC(role=actor.occupation, uuid=actor.uuid),
            SceneNPC(role=target.occupation, uuid=target.uuid),
        ],
    )
    return state, actor, target, location


def seed_kill_thread(state: GameState, actor: NPCCard, target: NPCCard) -> None:
    """Seed an open KILL thread joining ``actor`` and ``target``."""
    state.world_state.threads.append(
        WorldThread(
            description="brutus plots to kill marcus",
            category="personal",
            introduced_scene=1,
            involved_npcs=[actor.uuid, target.uuid],
            status="open",
        ),
    )
