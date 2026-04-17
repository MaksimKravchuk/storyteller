"""Tests for WAIT action handling in the Director execution flow."""

from __future__ import annotations

from unittest.mock import AsyncMock

import allure
import pytest

from cast.schemas.chronicler_response import ChroniclerResponse
from models.location import Location
from models.world_state import WorldThread
from tests.director_helpers import actor_reply, make_director, make_game_state, make_mock_agent, setup_npc

_NPC_A = "npc-1"
_GUARD = "guard"
_FORUM = "forum"


def _last_narrator_input(director):
    """Return the ``TurnOutputs`` most recently handed to the mocked Narrator."""
    narrator_call = director._cast.narrator.execute.call_args
    return narrator_call.kwargs["input_data"]


def _wait_route():
    return {
        "action_type": "WAIT",
        "is_aggressive": False,
        "targets": [],
        "needs_clarification": False,
        "delegate_to": ["narrator"],
    }


@allure.epic("Game Timeline")
@allure.feature("Wait action")
class TestWaitSkipsDialogue:
    @allure.story("Skips dialogue")
    @allure.title("WAIT action invokes the Actor only for the NPC's turn and never for dialogue generation")
    @pytest.mark.asyncio
    async def test_wait_does_not_call_actor_for_dialogue(self):
        gs = make_game_state()
        setup_npc(gs, _NPC_A, name="Guard", occupation=_GUARD)
        director = make_director(game_state=gs, route_response=_wait_route())
        mock_actor = AsyncMock()
        mock_actor.execute = AsyncMock(
            return_value=actor_reply(text='{"action": "watches", "type": "IDLE", "target": null}'),
        )
        director._actors[_NPC_A] = mock_actor

        await director.act("I wait")

        # Actor IS called for NPC turn, but NOT for dialogue.
        # Verify the call was for NPC turn (contains "It is" prompt), not dialogue.
        assert mock_actor.execute.call_count == 1
        call_input = mock_actor.execute.call_args.kwargs.get("input_data", "")
        assert "It is Guard's turn" in call_input

    @allure.story("Skips dialogue")
    @allure.title("WAIT action preserves the current scene and never triggers the SceneBuilder")
    @pytest.mark.asyncio
    async def test_wait_does_not_rebuild_scene(self):
        gs = make_game_state()
        director = make_director(game_state=gs, route_response=_wait_route())

        scene_before = gs.current_scene
        await director.act("wait")

        director._cast.scene_builder.execute.assert_not_called()
        assert gs.current_scene is scene_before


@allure.epic("Game Timeline")
@allure.feature("Wait action")
class TestWaitAdvancesTime:
    @allure.story("Advances clock")
    @allure.title("WAIT action advances the game clock to reflect time passing while the player holds still")
    @pytest.mark.asyncio
    async def test_wait_advances_game_clock(self):
        gs = make_game_state()
        clock_before = gs.game_clock
        director = make_director(game_state=gs, route_response=_wait_route())

        await director.act("wait")

        assert gs.game_clock > clock_before

    @allure.story("Advances clock")
    @allure.title("WAIT action counts as a real turn and increments the player's turn count")
    @pytest.mark.asyncio
    async def test_wait_increments_turn_count(self):
        gs = make_game_state()
        turns_before = gs.turn_count
        director = make_director(game_state=gs, route_response=_wait_route())

        await director.act("wait")

        assert gs.turn_count == turns_before + 1


@allure.epic("Game Timeline")
@allure.feature("Wait action")
class TestForcedWaitFromIncapacitation:
    @allure.story("Forced wait")
    @allure.title(
        "An unconscious player is forced into a wait regardless of the input action, short-circuiting the LLM router"
    )
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

    @allure.story("Forced wait")
    @allure.title("A stunned player is forced into a wait and the Narrator still produces output")
    @pytest.mark.asyncio
    async def test_stunned_player_is_forced_to_wait(self):
        gs = make_game_state()
        gs.player.physical_status = "stunned"
        director = make_director(game_state=gs)

        await director.act("look around")

        narrator_call = director._cast.narrator.execute.call_args
        assert narrator_call is not None

    @allure.story("Forced wait")
    @allure.title("A healthy player is routed normally and can trigger dialogue plus the NPC's reactive turn")
    @pytest.mark.asyncio
    async def test_healthy_player_routes_normally(self):
        gs = make_game_state()
        gs.player.physical_status = "healthy"
        setup_npc(gs, _NPC_A, name="Guard", occupation=_GUARD)
        route = {
            "action_type": "TALK",
            "targets": [_GUARD],
            "needs_clarification": False,
            "delegate_to": ["actor", "narrator"],
        }
        director = make_director(game_state=gs, route_response=route)
        mock_actor = AsyncMock()
        # First call: dialogue, second call: NPC turn
        mock_actor.execute = AsyncMock(
            side_effect=[
                actor_reply(text="Hello"),
                actor_reply(text='{"action": "watches", "type": "IDLE", "target": null}'),
            ],
        )
        director._actors[_NPC_A] = mock_actor

        await director.act("talk to the guard")

        # Actor called twice: dialogue + NPC turn
        assert mock_actor.execute.call_count == 2


@allure.epic("Game Timeline")
@allure.feature("Wait action")
class TestWaitSurfacesAmbientMaterial:
    @allure.story("Rich ambient context")
    @allure.title(
        "WAIT turn threads world-state content into raw_material so the Narrator is not called with an empty turn"
    )
    @pytest.mark.asyncio
    async def test_wait_surfaces_active_threads_to_narrator(self):
        gs = make_game_state()
        gs.player.location_id = _FORUM
        gs.locations[_FORUM] = Location(name="Forum", npcs_present=[])
        gs.world_state.threads.append(
            WorldThread(
                description="A riot is brewing in the streets",
                category="political",
                introduced_scene=0,
                involved_locations=[_FORUM],
            ),
        )
        director = make_director(game_state=gs, route_response=_wait_route())
        director._cast.world_chronicler = make_mock_agent(ChroniclerResponse())

        await director.act("wait")

        outputs_sent = _last_narrator_input(director)
        ctx = outputs_sent.wait_context
        assert ctx is not None
        assert ctx.active_threads
        assert any("riot is brewing" in thread.description for thread in ctx.active_threads)


@allure.epic("Game Timeline")
@allure.feature("Wait action")
class TestWaitKeywordShortCircuit:
    @allure.story("Keyword short-circuit")
    @allure.title("The '/wait' slash command routes to a wait turn without calling the LLM router")
    @pytest.mark.asyncio
    async def test_slash_wait_routes_without_llm(self):
        gs = make_game_state()
        director = make_director(game_state=gs)

        await director.act("/wait")

        # Narrator was called (game produced output)
        director._cast.narrator.execute.assert_called_once()
