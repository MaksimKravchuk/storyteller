"""Tests for NPC autonomous turn resolution."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest

from cast.dice import ContestType
from cast.npc_turn import NPCAction, NPCTurnResolver
from models.game_state import GameState
from models.npc_card import NPCCard
from models.scene import Scene, SceneNPC
from models.setting import Setting
from knowledge.graph import KnowledgeGraph

_NPC_UUID_A = "npc-a"
_NPC_UUID_B = "npc-b"
_GUARD = "Guard"
_MERCHANT = "Merchant"


def _make_gs() -> GameState:
    kg = KnowledgeGraph()
    return GameState(
        setting=Setting(name="Rome", time_period="1 AD", region="Italy", summary=""),
        knowledge_graph=kg,
    )


def _make_npc(uuid: str, name: str, mood: str = "neutral", status: str = "healthy", **attrs) -> NPCCard:
    npc = NPCCard(name=name, occupation="test", attributes=attrs)
    npc.uuid = uuid
    npc.current_mood = mood
    npc.physical_status = status
    return npc


def _make_scene(*npc_uuids: str) -> Scene:
    return Scene(
        location_id="forum",
        description="The bustling Forum.",
        npcs_present=[SceneNPC(role="npc", uuid=uid) for uid in npc_uuids],
    )


def _make_actor(response: dict) -> AsyncMock:
    """Create a mock Actor that returns JSON response."""
    mock = AsyncMock()
    mock.execute = AsyncMock(return_value=json.dumps(response))
    return mock


def _idle_response(npc_name: str = _GUARD) -> dict:
    return {"action": f"{npc_name} continues watching the crowd.", "type": "IDLE", "target": None}


def _attack_response(target: str = "player") -> dict:
    return {"action": "The guard draws his sword and lunges!", "type": "ATTACK", "target": target}


def _move_response() -> dict:
    return {"action": "The merchant packs up and walks away.", "type": "MOVE", "target": None}


def _talk_response(target: str = "player") -> dict:
    return {"action": "The merchant calls out to you.", "type": "TALK", "target": target}


class TestNPCTurnResolverInit:
    def test_creates_with_game_state_and_actors(self):
        gs = _make_gs()
        resolver = NPCTurnResolver(game_state=gs, actors={})
        assert resolver is not None


class TestNPCTurnResolverEmptyScene:
    @pytest.mark.asyncio
    async def test_no_scene_returns_empty(self):
        gs = _make_gs()
        gs.current_scene = None
        resolver = NPCTurnResolver(game_state=gs, actors={})
        actions = await resolver.resolve_npc_turns("Player looked around.")
        assert actions == []

    @pytest.mark.asyncio
    async def test_no_npcs_returns_empty(self):
        gs = _make_gs()
        gs.current_scene = Scene(location_id="empty", description="Empty room.", npcs_present=[])
        resolver = NPCTurnResolver(game_state=gs, actors={})
        actions = await resolver.resolve_npc_turns("Player waited.")
        assert actions == []


class TestNPCTurnResolverSingleNPC:
    @pytest.mark.asyncio
    async def test_single_npc_idle_action(self):
        gs = _make_gs()
        npc = _make_npc(_NPC_UUID_A, _GUARD)
        gs.npcs[_NPC_UUID_A] = npc
        gs.current_scene = _make_scene(_NPC_UUID_A)

        actor = _make_actor(_idle_response())
        resolver = NPCTurnResolver(game_state=gs, actors={_NPC_UUID_A: actor})

        actions = await resolver.resolve_npc_turns("Player waited.")

        assert len(actions) == 1
        assert actions[0].npc_uuid == _NPC_UUID_A
        assert actions[0].npc_name == _GUARD
        assert actions[0].action_type == "IDLE"
        assert actions[0].contest_roll is None

    @pytest.mark.asyncio
    async def test_npc_action_has_description(self):
        gs = _make_gs()
        npc = _make_npc(_NPC_UUID_A, _GUARD)
        gs.npcs[_NPC_UUID_A] = npc
        gs.current_scene = _make_scene(_NPC_UUID_A)

        actor = _make_actor(_idle_response())
        resolver = NPCTurnResolver(game_state=gs, actors={_NPC_UUID_A: actor})

        actions = await resolver.resolve_npc_turns("Player waited.")
        assert len(actions[0].action_description) > 0


class TestNPCTurnResolverSkipsIncapacitated:
    @pytest.mark.asyncio
    async def test_unconscious_npc_skipped(self):
        gs = _make_gs()
        npc = _make_npc(_NPC_UUID_A, _GUARD, status="unconscious")
        gs.npcs[_NPC_UUID_A] = npc
        gs.current_scene = _make_scene(_NPC_UUID_A)

        actor = _make_actor(_idle_response())
        resolver = NPCTurnResolver(game_state=gs, actors={_NPC_UUID_A: actor})

        actions = await resolver.resolve_npc_turns("Player waited.")
        assert actions == []
        actor.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_dead_npc_skipped(self):
        gs = _make_gs()
        npc = _make_npc(_NPC_UUID_A, _GUARD, status="dead")
        gs.npcs[_NPC_UUID_A] = npc
        gs.current_scene = _make_scene(_NPC_UUID_A)

        actor = _make_actor(_idle_response())
        resolver = NPCTurnResolver(game_state=gs, actors={_NPC_UUID_A: actor})

        actions = await resolver.resolve_npc_turns("Player waited.")
        assert actions == []


class TestNPCTurnResolverMultipleNPCs:
    @pytest.mark.asyncio
    async def test_multiple_npcs_resolve_simultaneously(self):
        gs = _make_gs()
        npc_a = _make_npc(_NPC_UUID_A, _GUARD)
        npc_b = _make_npc(_NPC_UUID_B, _MERCHANT)
        gs.npcs[_NPC_UUID_A] = npc_a
        gs.npcs[_NPC_UUID_B] = npc_b
        gs.current_scene = _make_scene(_NPC_UUID_A, _NPC_UUID_B)

        actor_a = _make_actor(_idle_response(_GUARD))
        actor_b = _make_actor(_talk_response())
        resolver = NPCTurnResolver(
            game_state=gs,
            actors={_NPC_UUID_A: actor_a, _NPC_UUID_B: actor_b},
        )

        actions = await resolver.resolve_npc_turns("Player explored.")

        assert len(actions) == 2
        names = {a.npc_name for a in actions}
        assert _GUARD in names
        assert _MERCHANT in names


class TestNPCTurnContestAgainstPlayer:
    @pytest.mark.asyncio
    async def test_attack_player_generates_contest(self):
        gs = _make_gs()
        npc = _make_npc(_NPC_UUID_A, _GUARD, combat_skill=5)
        gs.npcs[_NPC_UUID_A] = npc
        gs.current_scene = _make_scene(_NPC_UUID_A)

        actor = _make_actor(_attack_response("player"))
        resolver = NPCTurnResolver(game_state=gs, actors={_NPC_UUID_A: actor})

        actions = await resolver.resolve_npc_turns("Player insulted the guard.")

        assert len(actions) == 1
        assert actions[0].contest_roll is not None
        assert actions[0].contest_roll.contest_type == ContestType.COMBAT


class TestNPCTurnContestNPCvsNPC:
    @pytest.mark.asyncio
    async def test_npc_attacks_other_npc_generates_contest(self):
        gs = _make_gs()
        npc_a = _make_npc(_NPC_UUID_A, _GUARD, combat_skill=5)
        npc_b = _make_npc(_NPC_UUID_B, _MERCHANT, combat_skill=2)
        gs.npcs[_NPC_UUID_A] = npc_a
        gs.npcs[_NPC_UUID_B] = npc_b
        gs.current_scene = _make_scene(_NPC_UUID_A, _NPC_UUID_B)

        actor_a = _make_actor(_attack_response(_MERCHANT))
        actor_b = _make_actor(_idle_response(_MERCHANT))
        resolver = NPCTurnResolver(
            game_state=gs,
            actors={_NPC_UUID_A: actor_a, _NPC_UUID_B: actor_b},
        )

        actions = await resolver.resolve_npc_turns("Player watched.")

        guard_action = next(a for a in actions if a.npc_name == _GUARD)
        assert guard_action.contest_roll is not None
        assert guard_action.contest_roll.contest_type == ContestType.COMBAT


class TestNPCTurnSceneMutation:
    @pytest.mark.asyncio
    async def test_move_action_removes_npc_from_scene(self):
        gs = _make_gs()
        npc = _make_npc(_NPC_UUID_A, _MERCHANT)
        gs.npcs[_NPC_UUID_A] = npc
        gs.current_scene = _make_scene(_NPC_UUID_A)

        actor = _make_actor(_move_response())
        resolver = NPCTurnResolver(game_state=gs, actors={_NPC_UUID_A: actor})

        actions = await resolver.resolve_npc_turns("Player waited.")

        assert len(actions) == 1
        assert actions[0].action_type == "MOVE"
        # NPC should be removed from scene
        scene_uuids = [snpc.uuid for snpc in gs.current_scene.npcs_present]
        assert _NPC_UUID_A not in scene_uuids


class TestNPCActionDataclass:
    def test_npc_action_fields(self):
        action = NPCAction(
            npc_uuid="u1",
            npc_name="Guard",
            action_description="Stands guard.",
            action_type="IDLE",
            target=None,
            contest_roll=None,
        )
        assert action.npc_uuid == "u1"
        assert action.npc_name == "Guard"
        assert action.action_description == "Stands guard."
        assert action.action_type == "IDLE"
        assert action.target is None
        assert action.contest_roll is None
