"""Regression tests for KER-21 — inter-NPC visibility during aggressive turns.

When the player attacks an NPC, other scene NPCs must not converge on the
same template reaction (grab implement, shout, reach for whistle). These
tests verify the two-pronged fix:

1. Aggressive turns resolve NPCs sequentially (not via ``asyncio.gather``)
   so each NPC's Actor call sees what peers already did.
2. A "peer reactions" clause is injected into each subsequent NPC's prompt
   with an explicit "do not echo" directive.
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


class _OrderedActor:
    """Fake actor whose ``execute`` records enter/exit order in a shared log."""

    def __init__(self, response: dict, call_log: list[str], label: str) -> None:
        self._reply = ActorReply(text=json.dumps(response))
        self._call_log = call_log
        self._label = label

    async def execute(self, **_: Any) -> ActorReply:
        self._call_log.append("enter:{0}".format(self._label))
        await asyncio.sleep(0)
        self._call_log.append("exit:{0}".format(self._label))
        return self._reply


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


class _PromptCapturingActor:
    """Fake actor whose ``execute`` stores each ``input_data`` prompt verbatim."""

    def __init__(self, response: dict, captured: list[str]) -> None:
        self._reply = ActorReply(text=json.dumps(response))
        self._captured = captured

    async def execute(self, **kwargs: Any) -> ActorReply:
        self._captured.append(str(kwargs.get("input_data", "")))
        return self._reply


@allure.epic("NPC Interaction")
@allure.feature("NPC turn resolution")
class TestAggressiveTurnSerialization:
    @allure.story("Sequential resolution on aggression")
    @allure.title("Aggressive turns resolve NPCs strictly in sequence so each one sees the previous reaction")
    @pytest.mark.asyncio
    async def test_aggressive_turn_serializes_npc_resolution(self):
        gs = _make_gs()
        _build_three_npc_scene(gs)

        call_log: list[str] = []
        resolver = NPCTurnResolver(
            game_state=gs,
            actors={
                _NPC_UUID_A: _OrderedActor(_idle_response(_GUARD), call_log, "A"),
                _NPC_UUID_B: _OrderedActor(_idle_response(_MERCHANT), call_log, "B"),
                _NPC_UUID_C: _OrderedActor(_idle_response(_COOK), call_log, "C"),
            },
        )

        await resolver.resolve_npc_turns("Player attacks Ivan!", is_aggressive=True)

        # Expect strict non-interleaved ordering: enter:X → exit:X → enter:Y → exit:Y → ...
        for idx in range(0, len(call_log), 2):
            enter = call_log[idx]
            assert enter.startswith("enter:"), "call_log not in enter/exit pairs: {0}".format(call_log)
            assert call_log[idx + 1] == enter.replace("enter:", "exit:")

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


@allure.epic("NPC Interaction")
@allure.feature("NPC turn resolution")
class TestPeerActionsThreading:
    @allure.story("Peer-action visibility")
    @allure.title("A second NPC's prompt includes the first NPC's already-chosen action description")
    @pytest.mark.asyncio
    async def test_second_npc_sees_first_npc_action_in_prompt(self):
        gs = _make_gs()
        _build_three_npc_scene(gs)

        first_action_desc = "The guard draws his sword and lunges!"
        captured_a: list[str] = []
        captured_b: list[str] = []
        captured_c: list[str] = []
        resolver = NPCTurnResolver(
            game_state=gs,
            actors={
                _NPC_UUID_A: _PromptCapturingActor(
                    {"action": first_action_desc, "type": "ATTACK", "target": "player"},
                    captured_a,
                ),
                _NPC_UUID_B: _PromptCapturingActor(_idle_response(_MERCHANT), captured_b),
                _NPC_UUID_C: _PromptCapturingActor(_idle_response(_COOK), captured_c),
            },
        )

        await resolver.resolve_npc_turns("Player attacks Ivan!", is_aggressive=True)

        assert captured_b, "Merchant's actor was never invoked"
        assert first_action_desc in captured_b[0]
        assert _PEER_CLAUSE_MARKER in captured_b[0]
        assert _PEER_ECHO_WARNING in captured_b[0].lower()

    @allure.story("Peer-action visibility")
    @allure.title("The first NPC to resolve sees no peer clause — it is the first to react")
    @pytest.mark.asyncio
    async def test_first_npc_has_no_peer_clause(self):
        gs = _make_gs()
        _build_three_npc_scene(gs)

        captured_a: list[str] = []
        resolver = NPCTurnResolver(
            game_state=gs,
            actors={
                _NPC_UUID_A: _PromptCapturingActor(_idle_response(_GUARD), captured_a),
                _NPC_UUID_B: _PromptCapturingActor(_idle_response(_MERCHANT), []),
                _NPC_UUID_C: _PromptCapturingActor(_idle_response(_COOK), []),
            },
        )

        await resolver.resolve_npc_turns("Player attacks Ivan!", is_aggressive=True)

        assert captured_a, "Guard's actor was never invoked"
        assert _PEER_CLAUSE_MARKER not in captured_a[0]
