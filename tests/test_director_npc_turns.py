"""Tests for NPC turns integration in the Director execution flow."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import allure
import pytest

from models.npc_card import NPCCard
from tests.director_helpers import make_director, make_game_state

_NPC_A = "npc-1"
_GUARD = "Guard"


def _setup_guard(gs):
    """Register a guard NPC and its mock actor."""
    npc = NPCCard(name=_GUARD, occupation="city guard", attributes={"combat_skill": 5})
    npc.uuid = _NPC_A
    npc.current_mood = "neutral"
    gs.npcs[_NPC_A] = npc
    return npc


def _talk_route():
    return {
        "action_type": "TALK",
        "is_aggressive": False,
        "targets": [_GUARD],
        "needs_clarification": False,
        "delegate_to": ["actor", "narrator"],
    }


def _explore_route():
    return {
        "action_type": "EXPLORE",
        "is_aggressive": False,
        "targets": [],
        "needs_clarification": False,
        "delegate_to": ["scene_builder", "narrator"],
    }


def _examine_route():
    return {
        "action_type": "EXAMINE",
        "is_aggressive": False,
        "targets": ["fountain"],
        "needs_clarification": False,
        "delegate_to": ["narrator"],
    }


def _idle_json():
    return json.dumps({"action": "The guard watches the crowd.", "type": "IDLE", "target": None})


@allure.epic("NPC Interaction")
@allure.feature("NPC turn integration")
class TestDirectorCallsNPCTurns:
    @allure.story("NPC turn after talk")
    @allure.title("After a TALK action the actor is invoked twice: once for dialogue and once for the NPC turn")
    @pytest.mark.asyncio
    async def test_npc_turns_called_after_talk(self):
        gs = make_game_state()
        _setup_guard(gs)
        director = make_director(game_state=gs, route_response=_talk_route())

        # Mock actor for dialogue + NPC turn (returns dialogue first, then turn JSON)
        mock_actor = AsyncMock()
        mock_actor.execute = AsyncMock(side_effect=["Hello traveler.", _idle_json()])
        director._actors[_NPC_A] = mock_actor

        await director.act("talk to the guard")

        # Actor should be called twice: once for dialogue, once for NPC turn
        assert mock_actor.execute.call_count == 2

    @allure.story("NPC turn after wait")
    @allure.title("A /wait action runs a single NPC turn per scene actor with no dialogue call")
    @pytest.mark.asyncio
    async def test_npc_turns_called_after_wait(self):
        gs = make_game_state()
        _setup_guard(gs)
        director = make_director(game_state=gs)

        mock_actor = AsyncMock()
        mock_actor.execute = AsyncMock(return_value=_idle_json())
        director._actors[_NPC_A] = mock_actor

        await director.act("/wait")

        # Actor called once for NPC turn (no dialogue on WAIT)
        assert mock_actor.execute.call_count == 1

    @allure.story("NPC turn after examine")
    @allure.title("An EXAMINE action is not a turn-counting action and does not trigger any NPC turns")
    @pytest.mark.asyncio
    async def test_npc_turns_not_called_on_examine(self):
        gs = make_game_state()
        _setup_guard(gs)
        director = make_director(game_state=gs, route_response=_examine_route())

        mock_actor = AsyncMock()
        mock_actor.execute = AsyncMock(return_value=_idle_json())
        director._actors[_NPC_A] = mock_actor

        await director.act("look at the fountain")

        # EXAMINE is not a turn-counting action, so no NPC turns
        mock_actor.execute.assert_not_called()


@allure.epic("NPC Interaction")
@allure.feature("NPC turn integration")
class TestNPCTurnsPassedToNarrator:
    @allure.story("NPC turns in narrator input")
    @allure.title("Resolved NPC turns are passed to the narrator under the 'npc_turns' field with NPC names")
    @pytest.mark.asyncio
    async def test_npc_turns_in_narrator_input(self):
        gs = make_game_state()
        _setup_guard(gs)
        director = make_director(game_state=gs)

        mock_actor = AsyncMock()
        mock_actor.execute = AsyncMock(return_value=_idle_json())
        director._actors[_NPC_A] = mock_actor

        await director.act("/wait")

        narrator_call = director._cast.narrator.execute.call_args
        raw_outputs = narrator_call.kwargs.get("input_data") or narrator_call.args[0]
        assert raw_outputs.npc_turns
        assert len(raw_outputs.npc_turns) == 1
        assert raw_outputs.npc_turns[0].npc_name == _GUARD
