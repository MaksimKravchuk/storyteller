"""Tests for WAIT action handling in the Director execution flow."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from tests.director_helpers import make_director, make_game_state, setup_npc

_NPC_A = "npc-1"
_GUARD = "guard"


def _wait_route():
    return {
        "action_type": "WAIT",
        "is_aggressive": False,
        "targets": [],
        "needs_clarification": False,
        "delegate_to": ["narrator"],
    }


class TestWaitSkipsDialogue:
    @pytest.mark.asyncio
    async def test_wait_does_not_call_actor(self):
        gs = make_game_state()
        npc = setup_npc(gs, _NPC_A, name="Guard", occupation=_GUARD)
        director = make_director(game_state=gs, route_response=_wait_route())
        mock_actor = AsyncMock()
        mock_actor.execute = AsyncMock(return_value="Hello")
        director._actors[_NPC_A] = mock_actor

        await director.act("I wait")

        mock_actor.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_wait_does_not_rebuild_scene(self):
        gs = make_game_state()
        director = make_director(game_state=gs, route_response=_wait_route())

        scene_before = gs.current_scene
        await director.act("wait")

        director._cast.scene_builder.execute.assert_not_called()
        assert gs.current_scene is scene_before


class TestWaitAdvancesTime:
    @pytest.mark.asyncio
    async def test_wait_advances_game_clock(self):
        gs = make_game_state()
        clock_before = gs.game_clock
        director = make_director(game_state=gs, route_response=_wait_route())

        await director.act("wait")

        assert gs.game_clock > clock_before

    @pytest.mark.asyncio
    async def test_wait_increments_turn_count(self):
        gs = make_game_state()
        turns_before = gs.turn_count
        director = make_director(game_state=gs, route_response=_wait_route())

        await director.act("wait")

        assert gs.turn_count == turns_before + 1


class TestForcedWaitFromIncapacitation:
    @pytest.mark.asyncio
    async def test_unconscious_player_is_forced_to_wait(self):
        gs = make_game_state()
        gs.player.physical_status = "unconscious"
        director = make_director(game_state=gs)

        await director.act("I attack the guard")

        # The LLM router should NOT have been called (short-circuited)
        # and the narrator should have been called with wait content
        narrator_call = director._cast.narrator.execute.call_args
        assert narrator_call is not None

    @pytest.mark.asyncio
    async def test_stunned_player_is_forced_to_wait(self):
        gs = make_game_state()
        gs.player.physical_status = "stunned"
        director = make_director(game_state=gs)

        await director.act("look around")

        narrator_call = director._cast.narrator.execute.call_args
        assert narrator_call is not None

    @pytest.mark.asyncio
    async def test_healthy_player_routes_normally(self):
        gs = make_game_state()
        gs.player.physical_status = "healthy"
        npc = setup_npc(gs, _NPC_A, name="Guard", occupation=_GUARD)
        route = {
            "action_type": "TALK",
            "targets": [_GUARD],
            "needs_clarification": False,
            "delegate_to": ["actor", "narrator"],
        }
        director = make_director(game_state=gs, route_response=route)
        mock_actor = AsyncMock()
        mock_actor.execute = AsyncMock(return_value="Hello")
        director._actors[_NPC_A] = mock_actor

        await director.act("talk to the guard")

        mock_actor.execute.assert_called_once()


class TestWaitKeywordShortCircuit:
    @pytest.mark.asyncio
    async def test_slash_wait_routes_without_llm(self):
        gs = make_game_state()
        director = make_director(game_state=gs)

        await director.act("/wait")

        # Narrator was called (game produced output)
        director._cast.narrator.execute.assert_called_once()
