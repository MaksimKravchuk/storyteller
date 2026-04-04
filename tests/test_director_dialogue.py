"""Tests for Director NPC dialogue deduplication and NPC generator integration."""

from __future__ import annotations

from unittest.mock import AsyncMock

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


class TestDuplicateNPCNames:
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

        director._actors[_NPC_A] = make_mock_agent(None)
        director._actors[_NPC_A].execute = AsyncMock(
            side_effect=lambda input_data, context: _mood_side_effect(input_data, context, gs),
        )
        director._actors[_NPC_B] = make_mock_agent(None)
        director._actors[_NPC_B].execute = AsyncMock(
            side_effect=lambda input_data, context: _mood_side_effect(input_data, context, gs),
        )

        from tests.test_director_retaliation import _make_aggression_stub, _run_patched

        await _run_patched(
            _make_aggression_stub(True),
            director.act("attack the guard"),
        )
        calls_a = director._actors[_NPC_A].execute.call_count
        calls_b = director._actors[_NPC_B].execute.call_count
        # 1 dialogue (deduped) + 1 retaliation + 2 NPC turns = 4
        assert calls_a + calls_b == 4


class TestNPCGeneratorDeduplication:
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
        assert "new_npcs" in input_data
        assert any("Merchant" in desc for desc in input_data["new_npcs"])
