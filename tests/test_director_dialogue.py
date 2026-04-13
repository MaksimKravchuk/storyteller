"""Tests for Director NPC dialogue deduplication and NPC generator integration."""

from __future__ import annotations

from unittest.mock import AsyncMock

import allure
import pytest

from llm.message import LLMResponse
from models.game_state import GameState
from models.npc_card import NPCCard
from models.scene import Scene, SceneNPC
from tests.director_helpers import make_director, make_game_state, make_mock_agent, make_setting, setup_npc

_HOSTILE = "hostile"
_NPC_A = "npc-1"
_NPC_B = "npc-2"
_GUARD = "Guard"
_NIGHT_GUARD = "night guard"
_DOCK_GUARD = "dock guard"
_ACTION_TYPE = "action_type"
_TALK = "TALK"
_MOVE = "MOVE"
_TARGETS = "targets"
_NEEDS_CLARIFICATION = "needs_clarification"
_DELEGATE_TO = "delegate_to"
_ACTOR = "actor"
_NARRATOR = "narrator"


def _mood_side_effect(input_data, context, gs):
    """Side effect that sets both NPCs to hostile mood."""
    gs.npcs[_NPC_A].current_mood = _HOSTILE
    gs.npcs[_NPC_B].current_mood = _HOSTILE
    return "*blocks*\n[MOOD: {0}]".format(_HOSTILE)


@allure.epic("NPC Interaction")
@allure.feature("Dialogue routing")
class TestDuplicateNPCNames:
    @allure.story("Duplicate NPC names")
    @allure.title("Talking to 'the guard' when two guards share that name triggers dialogue for only one of them")
    @pytest.mark.asyncio
    async def test_duplicate_names_one_actor_called(self):
        gs = make_game_state()
        setup_npc(gs, _NPC_A, name=_GUARD, occupation=_NIGHT_GUARD, mood="")
        setup_npc(gs, _NPC_B, name=_GUARD, occupation=_DOCK_GUARD, mood="")
        gs.current_scene = Scene(
            location_id="docks",
            description="The docks.",
            npcs_present=[
                SceneNPC(role=_NIGHT_GUARD, uuid=_NPC_A),
                SceneNPC(role=_DOCK_GUARD, uuid=_NPC_B),
            ],
        )
        director = make_director(
            game_state=gs,
            route_response={
                _ACTION_TYPE: _TALK,
                _TARGETS: ("guard",),
                _NEEDS_CLARIFICATION: False,
                _DELEGATE_TO: [_ACTOR, _NARRATOR],
            },
        )
        director._actors[_NPC_A] = make_mock_agent("Hello.")
        director._actors[_NPC_B] = make_mock_agent("Hi there.")
        await director.act("talk to the guard")
        calls_a = director._actors[_NPC_A].execute.call_count
        calls_b = director._actors[_NPC_B].execute.call_count
        # 1 dialogue call (deduped by name) + 2 NPC turn calls (both NPCs in scene)
        assert calls_a + calls_b == 3

    @allure.story("Duplicate NPC names")
    @allure.title("Attacking 'the guard' when two guards exist runs dialogue once and no redundant retaliation")
    @pytest.mark.asyncio
    async def test_retaliation_skips_duplicate_names(self):
        gs = make_game_state()
        setup_npc(gs, _NPC_A, name=_GUARD, occupation=_NIGHT_GUARD, attributes={"combat_skill": 5})
        setup_npc(gs, _NPC_B, name=_GUARD, occupation=_DOCK_GUARD, attributes={"combat_skill": 5})
        gs.current_scene = Scene(
            location_id="docks",
            description="The docks.",
            npcs_present=[
                SceneNPC(role=_NIGHT_GUARD, uuid=_NPC_A),
                SceneNPC(role=_DOCK_GUARD, uuid=_NPC_B),
            ],
        )
        director = make_director(
            game_state=gs,
            route_response={
                _ACTION_TYPE: "INTERACT",
                "is_aggressive": True,
                _TARGETS: ("guard",),
                _NEEDS_CLARIFICATION: False,
                _DELEGATE_TO: [_ACTOR, _NARRATOR],
            },
        )

        mood_exec = AsyncMock(
            side_effect=lambda input_data, context: _mood_side_effect(input_data, context, gs),
        )
        actor_a = make_mock_agent(None)
        actor_a.execute = mood_exec
        director._actors[_NPC_A] = actor_a
        actor_b = make_mock_agent(None)
        actor_b.execute = AsyncMock(
            side_effect=lambda input_data, context: _mood_side_effect(input_data, context, gs),
        )
        director._actors[_NPC_B] = actor_b

        from tests.test_director_retaliation import _make_aggression_stub, _run_patched

        await _run_patched(
            _make_aggression_stub(True),
            director.act("attack the guard"),
        )
        calls_a = director._actors[_NPC_A].execute.call_count
        calls_b = director._actors[_NPC_B].execute.call_count
        # 1 dialogue (deduped, name-match → only one guard) + 2 NPC turns = 3.
        # No redundant retaliation: the dialogue combat roll already resolved
        # the aggression, see test_aggressive_target_not_retaliated_twice.
        assert calls_a + calls_b == 3


@allure.epic("NPC Interaction")
@allure.feature("Dialogue routing")
class TestNPCGeneratorDeduplication:
    @allure.story("NPC generator integration")
    @allure.title("Talking to a brand new target NPC calls the NPCGenerator exactly once")
    @pytest.mark.asyncio
    async def test_new_target_npc_generates_exactly_once(self):
        from knowledge.graph import KnowledgeGraph

        gs = GameState(setting=make_setting(), knowledge_graph=KnowledgeGraph())
        gs.current_scene = Scene(location_id="market", description="The market.", npcs_present=[])
        generated = NPCCard(name="Blacksmith", occupation="blacksmith")
        generated.uuid = "gen-1"

        npc_gen = AsyncMock()
        npc_gen.execute = AsyncMock(return_value=[generated])
        director = make_director(
            game_state=gs,
            route_response={
                _ACTION_TYPE: _TALK,
                _TARGETS: ["blacksmith"],
                _NEEDS_CLARIFICATION: False,
                _DELEGATE_TO: ["npc_generator", _ACTOR, _NARRATOR],
            },
        )
        director._cast.npc_generator = npc_gen
        director.llm_client.send_message = AsyncMock(
            return_value=LLMResponse(body="I'm the blacksmith!", model="test", usage={})
        )
        await director.act("talk to the blacksmith")
        assert npc_gen.execute.call_count == 1

    @allure.story("NPC generator integration")
    @allure.title("Talking to an NPC already in game state does not call the NPCGenerator at all")
    @pytest.mark.asyncio
    async def test_existing_npc_no_generator_call(self):
        gs = make_game_state()
        npc = NPCCard(name=_GUARD, occupation="city guard")
        npc.uuid = _NPC_A
        gs.npcs[_NPC_A] = npc

        npc_gen = AsyncMock()
        npc_gen.execute = AsyncMock(return_value=[])
        director = make_director(
            game_state=gs,
            route_response={
                _ACTION_TYPE: _TALK,
                _TARGETS: ("guard",),
                _NEEDS_CLARIFICATION: False,
                _DELEGATE_TO: ["npc_generator", _ACTOR, _NARRATOR],
            },
        )
        director._cast.npc_generator = npc_gen
        mock_actor = AsyncMock()
        mock_actor.execute = AsyncMock(return_value="Hello!")
        director._actors[_NPC_A] = mock_actor
        await director.act("talk to the guard")
        assert npc_gen.execute.call_count == 0

    @allure.story("NPC generator integration")
    @allure.title("An item name in the targets list (e.g. 'меч') never triggers NPC generation or scene insertion")
    @pytest.mark.asyncio
    async def test_item_target_no_npc_generation(self):
        """Item name 'меч' must NOT trigger NPCGenerator."""
        gs = make_game_state()
        setup_npc(gs, _NPC_A, name=_GUARD, occupation="city guard")

        npc_gen = AsyncMock()
        npc_gen.execute = AsyncMock(return_value=[])
        director = make_director(
            game_state=gs,
            route_response={
                _ACTION_TYPE: "INTERACT",
                "is_aggressive": True,
                _TARGETS: [_GUARD, "меч"],
                _NEEDS_CLARIFICATION: False,
                _DELEGATE_TO: [_ACTOR, _NARRATOR],
            },
        )
        director._cast.npc_generator = npc_gen
        director._actors[_NPC_A] = make_mock_agent("*blocks*")

        await director.act("grab his sword")

        assert npc_gen.execute.call_count == 0
        scene_roles = [snpc.role for snpc in gs.current_scene.npcs_present]
        assert "меч" not in scene_roles

    @allure.story("NPC generator integration")
    @allure.title("Newly generated NPCs are announced to the narrator via the new_npcs input field")
    @pytest.mark.asyncio
    async def test_new_npc_announced_to_narrator(self):
        from knowledge.graph import KnowledgeGraph

        gs = GameState(setting=make_setting(), knowledge_graph=KnowledgeGraph())
        gs.current_scene = Scene(location_id="market", description="The market.", npcs_present=[])
        generated = NPCCard(name="Merchant", occupation="cloth merchant")
        generated.uuid = "gen-2"
        director = make_director(
            game_state=gs,
            route_response={
                _ACTION_TYPE: _TALK,
                _TARGETS: ["merchant"],
                _NEEDS_CLARIFICATION: False,
                _DELEGATE_TO: ["npc_generator", _NARRATOR],
            },
        )
        director._cast.npc_generator = make_mock_agent([generated])
        director.llm_client.send_message = AsyncMock(
            return_value=LLMResponse(body="Fine silks!", model="test", usage={})
        )
        await director.act("talk to the merchant")
        narrator_call = director._cast.narrator.execute.call_args
        input_data = narrator_call.kwargs.get("input_data") or narrator_call.args[0]
        assert input_data.new_npcs
        assert any("Merchant" in desc for desc in input_data.new_npcs)


@allure.epic("NPC Interaction")
@allure.feature("Dialogue routing")
class TestMoveToExistingNPCNoSceneRebuild:
    """MOVE targeting an NPC already present in the scene must NOT trigger
    SceneBuilder.  Observed in production: 'иду к Луций Флавий Марцелл'
    caused a full scene rebuild (3 NPCGenerator + 3 ItemGenerator calls)
    even though the NPC was already in the current scene."""

    @allure.story("Move-to-NPC routing")
    @allure.title("Moving toward an NPC already in the current scene skips both SceneBuilder and NPCGenerator")
    @pytest.mark.asyncio
    async def test_move_to_scene_npc_skips_scene_builder(self):
        gs = make_game_state()
        setup_npc(gs, _NPC_A, name=_GUARD, occupation="city guard")

        director = make_director(
            game_state=gs,
            route_response={
                _ACTION_TYPE: _MOVE,
                _TARGETS: [_GUARD],
                _NEEDS_CLARIFICATION: False,
                _DELEGATE_TO: [_NARRATOR, _ACTOR],
            },
        )
        mock_actor = AsyncMock()
        mock_actor.execute = AsyncMock(return_value="Halt!")
        director._actors[_NPC_A] = mock_actor

        await director.act("walk to the guard")

        # SceneBuilder must NOT be called — the target NPC is already here
        director._cast.scene_builder.execute.assert_not_called()
        # NPCGenerator must NOT be called — no new NPCs needed
        director._cast.npc_generator.execute.assert_not_called()
