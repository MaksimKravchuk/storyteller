"""NPC turn concurrency: every turn, aggressive or routine, resolves bystander reactions at once.

KER-21 once serialised aggressive turns so each NPC saw its peers' reactions;
that cost ~1.6 s per bystander on the slowest turn type and was dropped for latency.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from uuid import UUID

import allure
import pytest

from cast.npc_turn import NPCTurnResolver
from cast.schemas.actor_reply import ActorReply
from knowledge.graph import KnowledgeGraph
from models import game_state as gs_mod, npc_card as npc_card_mod, scene as scene_mod, setting as setting_mod
from tests._uuid_helpers import make_uuid

GameState = gs_mod.GameState
NPCCard = npc_card_mod.NPCCard
Scene = scene_mod.Scene
SceneNPC = scene_mod.SceneNPC
Setting = setting_mod.Setting

_NPC_UUID_A = make_uuid("npc-a")
_NPC_UUID_B = make_uuid("npc-b")
_NPC_UUID_C = make_uuid("npc-c")
_GUARD = "Guard"
_MERCHANT = "Merchant"
_COOK = "Cook"

_PEER_CLAUSE_MARKER = "Other NPCs in this scene have already reacted"
_PEER_ECHO_WARNING = "do not echo"


def _make_gs() -> GameState:
    kg = KnowledgeGraph()
    return GameState(
        setting=Setting(name="Rome", time_period="1 AD", region="Italy", summary=""),
        knowledge_graph=kg,
    )


def _make_npc(uuid: UUID, name: str) -> NPCCard:
    npc = NPCCard(name=name, occupation="test")
    npc.uuid = uuid
    npc.current_mood = "neutral"
    npc.physical_status = "healthy"
    return npc


def _idle_response(npc_name: str) -> dict:
    return {"action": "{0} continues watching the crowd.".format(npc_name), "type": "IDLE", "target": None}


def _build_three_npc_scene(gs: GameState) -> None:
    """Register three distinct NPCs (guard / merchant / cook) in the current scene."""
    gs.npcs[_NPC_UUID_A] = _make_npc(_NPC_UUID_A, _GUARD)
    gs.npcs[_NPC_UUID_B] = _make_npc(_NPC_UUID_B, _MERCHANT)
    gs.npcs[_NPC_UUID_C] = _make_npc(_NPC_UUID_C, _COOK)
    gs.current_scene = Scene(
        location_id=make_uuid("forum"),
        description="The bustling Forum.",
        npcs_present=[
            SceneNPC(role="npc", uuid=_NPC_UUID_A),
            SceneNPC(role="npc", uuid=_NPC_UUID_B),
            SceneNPC(role="npc", uuid=_NPC_UUID_C),
        ],
    )


class _ConcurrencyTrackingActor:
    """Fake actor whose ``execute`` records peak simultaneous in-flight calls."""

    def __init__(self, response: dict, tracker: dict) -> None:
        self._reply = ActorReply(text=json.dumps(response))
        self._tracker = tracker

    async def execute(self, **_: Any) -> ActorReply:
        self._tracker["active"] = self._tracker.get("active", 0) + 1
        self._tracker["max_active"] = max(self._tracker.get("max_active", 0), self._tracker["active"])
        await asyncio.sleep(0)
        self._tracker["active"] -= 1
        return self._reply


@allure.epic("NPC Interaction")
@allure.feature("NPC turn resolution")
class TestAggressiveTurnSerialization:
    @allure.story("Parallel on aggression")
    @allure.title("Aggressive turns resolve NPC reactions concurrently, like routine turns")
    @pytest.mark.asyncio
    async def test_aggressive_turn_runs_npcs_concurrently(self):
        gs = _make_gs()
        _build_three_npc_scene(gs)

        tracker: dict = {"active": 0, "max_active": 0}
        resolver = NPCTurnResolver(
            game_state=gs,
            actors={
                _NPC_UUID_A: _ConcurrencyTrackingActor(_idle_response(_GUARD), tracker),
                _NPC_UUID_B: _ConcurrencyTrackingActor(_idle_response(_MERCHANT), tracker),
                _NPC_UUID_C: _ConcurrencyTrackingActor(_idle_response(_COOK), tracker),
            },
        )

        actions = await resolver.resolve_npc_turns("Player attacks Ivan!", is_aggressive=True)

        assert tracker["max_active"] == 3, "All three bystanders should react at once, not one after another."
        assert [action.npc_name for action in actions] == [_GUARD, _MERCHANT, _COOK]

    @allure.story("Parallel on routine turns")
    @allure.title("Non-aggressive turns keep using asyncio.gather so multiple NPCs act concurrently")
    @pytest.mark.asyncio
    async def test_non_aggressive_keeps_parallel(self):
        gs = _make_gs()
        _build_three_npc_scene(gs)

        tracker: dict = {"active": 0, "max_active": 0}
        resolver = NPCTurnResolver(
            game_state=gs,
            actors={
                _NPC_UUID_A: _ConcurrencyTrackingActor(_idle_response(_GUARD), tracker),
                _NPC_UUID_B: _ConcurrencyTrackingActor(_idle_response(_MERCHANT), tracker),
                _NPC_UUID_C: _ConcurrencyTrackingActor(_idle_response(_COOK), tracker),
            },
        )

        await resolver.resolve_npc_turns("Player waits.", is_aggressive=False)

        assert tracker["max_active"] > 1, "Non-aggressive turns should still run NPC actors concurrently."
