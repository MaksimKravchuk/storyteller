"""Tests for NPC autonomous turn resolution."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import allure
import pytest

from cast.dice import ContestType
from cast.npc_turn import NPCAction, NPCTurnResolver, _build_turn_prompt
from cast.schemas.actor_reply import ActorReply
from knowledge.graph import KnowledgeGraph
from models import game_state as gs_mod, npc_card as npc_card_mod, scene as scene_mod, setting as setting_mod

GameState = gs_mod.GameState
NPCCard = npc_card_mod.NPCCard
Scene = scene_mod.Scene
SceneNPC = scene_mod.SceneNPC
Setting = setting_mod.Setting

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
    """Create a mock Actor that returns JSON response wrapped in ActorReply."""
    mock = AsyncMock()
    mock.execute = AsyncMock(return_value=ActorReply(text=json.dumps(response)))
    return mock


def _idle_response(npc_name: str = _GUARD) -> dict:
    return {"action": f"{npc_name} continues watching the crowd.", "type": "IDLE", "target": None}


def _attack_response(target: str = "player") -> dict:
    return {"action": "The guard draws his sword and lunges!", "type": "ATTACK", "target": target}


def _move_response() -> dict:
    return {"action": "The merchant packs up and walks away.", "type": "MOVE", "target": None}


def _talk_response(target: str = "player") -> dict:
    return {"action": "The merchant calls out to you.", "type": "TALK", "target": target}


@allure.epic("NPC Interaction")
@allure.feature("NPC turn resolution")
class TestNPCTurnResolverInit:
    @allure.story("Resolver construction")
    @allure.title("NPCTurnResolver can be constructed with an empty actors dict and any game state")
    def test_creates_with_game_state_and_actors(self):
        gs = _make_gs()
        resolver = NPCTurnResolver(game_state=gs, actors={})
        assert resolver is not None


@allure.epic("NPC Interaction")
@allure.feature("NPC turn resolution")
class TestNPCTurnResolverEmptyScene:
    @allure.story("Empty scene")
    @allure.title("With no current_scene at all, NPC turn resolution returns an empty action list")
    @pytest.mark.asyncio
    async def test_no_scene_returns_empty(self):
        gs = _make_gs()
        gs.current_scene = None
        resolver = NPCTurnResolver(game_state=gs, actors={})
        actions = await resolver.resolve_npc_turns("Player looked around.")
        assert actions == []

    @allure.story("Empty scene")
    @allure.title("A scene with no NPCs present yields no NPC turn actions")
    @pytest.mark.asyncio
    async def test_no_npcs_returns_empty(self):
        gs = _make_gs()
        gs.current_scene = Scene(location_id="empty", description="Empty room.", npcs_present=[])
        resolver = NPCTurnResolver(game_state=gs, actors={})
        actions = await resolver.resolve_npc_turns("Player waited.")
        assert actions == []


@allure.epic("NPC Interaction")
@allure.feature("NPC turn resolution")
class TestNPCTurnResolverSingleNPC:
    @allure.story("Action parsing")
    @allure.title("A single NPC returning an IDLE JSON turn yields one action with no contest roll")
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

    @allure.story("Action parsing")
    @allure.title("Every resolved NPC turn populates a non-empty action_description string")
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


@allure.epic("NPC Interaction")
@allure.feature("NPC turn resolution")
class TestNPCTurnResolverSkipsIncapacitated:
    @allure.story("Incapacitation")
    @allure.title("An unconscious NPC is skipped entirely and its actor is never called")
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

    @allure.story("Incapacitation")
    @allure.title("An NPC with physical_status 'dead' produces no turn action")
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


@allure.epic("NPC Interaction")
@allure.feature("NPC turn resolution")
class TestNPCTurnResolverMultipleNPCs:
    @allure.story("Concurrent resolution")
    @allure.title("Multiple NPCs in a scene all resolve their turns in parallel and all appear in the result")
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


@allure.epic("NPC Interaction")
@allure.feature("NPC turn resolution")
class TestNPCTurnContestAgainstPlayer:
    @allure.story("Target selection")
    @allure.title("An NPC ATTACK turn targeting the player generates a COMBAT contest roll on that action")
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


@allure.epic("NPC Interaction")
@allure.feature("NPC turn resolution")
class TestNPCTurnContestNPCvsNPC:
    @allure.story("Target selection")
    @allure.title("An NPC attacking another NPC generates a COMBAT contest roll between the two NPCs")
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


@allure.epic("NPC Interaction")
@allure.feature("NPC turn resolution")
class TestNPCTurnSceneMutation:
    @allure.story("Scene mutation")
    @allure.title("An NPC MOVE turn removes the NPC from the current scene's npcs_present list")
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


@allure.epic("NPC Interaction")
@allure.feature("NPC turn resolution")
class TestNPCTurnResolverErrorHandling:
    @allure.story("Error handling")
    @allure.title("An LLM failure for one NPC does not prevent other NPCs from completing their turns")
    @pytest.mark.asyncio
    async def test_one_npc_failure_does_not_kill_others(self):
        gs = _make_gs()
        guard = _make_npc(_NPC_UUID_A, _GUARD)
        merchant = _make_npc(_NPC_UUID_B, _MERCHANT)
        gs.npcs[_NPC_UUID_A] = guard
        gs.npcs[_NPC_UUID_B] = merchant
        gs.current_scene = _make_scene(_NPC_UUID_A, _NPC_UUID_B)

        failing_actor = AsyncMock()
        failing_actor.execute = AsyncMock(side_effect=RuntimeError("LLM timeout"))
        ok_actor = _make_actor(_idle_response(_MERCHANT))

        resolver = NPCTurnResolver(
            game_state=gs,
            actors={_NPC_UUID_A: failing_actor, _NPC_UUID_B: ok_actor},
        )

        actions = await resolver.resolve_npc_turns("Player waited.")

        assert len(actions) == 1
        assert actions[0].npc_name == _MERCHANT


@allure.epic("NPC Interaction")
@allure.feature("NPC turn resolution")
class TestBuildTurnPromptNudgeRemoval:
    """The "Most turns are routine" nudge flattened every autonomous
    decision toward IDLE even when the NPC's mood, relationships, and
    inventory supplied ample motive. The character data drives the
    choice on its own.
    """

    @allure.story("Routine-nudge removal")
    @allure.title("_build_turn_prompt does not contain the 'Most turns are routine' clause")
    def test_prompt_does_not_contain_routine_nudge(self):
        gs = _make_gs()
        npc = _make_npc(_NPC_UUID_A, _GUARD)
        gs.npcs[_NPC_UUID_A] = npc
        gs.current_scene = _make_scene(_NPC_UUID_A)

        prompt = _build_turn_prompt(npc, "Player waited.", gs)

        assert "Most turns are routine" not in prompt
        assert "Only take dramatic action" not in prompt

    @allure.story("Routine-nudge removal")
    @allure.title("_build_turn_prompt still anchors the NPC to 'Stay in character.'")
    def test_prompt_preserves_stay_in_character(self):
        gs = _make_gs()
        npc = _make_npc(_NPC_UUID_A, _GUARD)
        gs.npcs[_NPC_UUID_A] = npc
        gs.current_scene = _make_scene(_NPC_UUID_A)

        prompt = _build_turn_prompt(npc, "Player waited.", gs)

        assert "Stay in character." in prompt


@allure.epic("NPC Interaction")
@allure.feature("NPC turn resolution")
class TestNPCActionDataclass:
    @allure.story("NPCAction dataclass")
    @allure.title("NPCAction dataclass stores uuid, name, description, type, target, and optional contest roll")
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
