"""Tests for Director turn counting, scene changes, and conversation log."""

from __future__ import annotations

import asyncio

import allure
import pytest

from cast.constants import SCENE_CHANGING_ACTIONS, TURN_COUNTING_ACTIONS
from models.scene import Scene, SceneNPC
from tests.director_helpers import make_director, make_game_state, route_plan as _route

_TALK = "TALK"
_SUMMARY_MAX_LENGTH = 500


async def _run_action_check(action_type):
    """Run a single action type and verify turn_count increments."""
    gs = make_game_state()
    director = make_director(game_state=gs, route_response=_route(action_type))
    await director.act("do something")
    assert gs.turn_count == 1, f"{action_type} should increment turn_count"


@allure.epic("Game Timeline")
@allure.feature("Action routing")
class TestTurnCounting:
    @allure.story("Turn counting")
    @allure.title("TALK actions increment the player's turn count")
    @pytest.mark.asyncio
    async def test_turn_increments_on_talk(self):
        director = make_director(route_response=_route(_TALK))
        await director.act("talk to someone")
        assert director._game_state.turn_count == 1

    @allure.story("Turn counting")
    @allure.title("INTERACT actions increment the player's turn count")
    @pytest.mark.asyncio
    async def test_turn_increments_on_interact(self):
        director = make_director(route_response=_route("INTERACT"))
        await director.act("open the door")
        assert director._game_state.turn_count == 1

    @allure.story("Turn counting")
    @allure.title("EXAMINE actions are free and do not advance the turn count")
    @pytest.mark.asyncio
    async def test_turn_does_not_increment_on_examine(self):
        director = make_director(route_response=_route("EXAMINE"))
        await director.act("look at the fountain")
        assert director._game_state.turn_count == 0

    @allure.story("Turn counting")
    @allure.title("OTHER free-form actions do not advance the turn count")
    @pytest.mark.asyncio
    async def test_turn_does_not_increment_on_other(self):
        director = make_director(route_response=_route("OTHER"))
        await director.act("hum a tune")
        assert director._game_state.turn_count == 0

    @allure.story("Clarification flow")
    @allure.title("A turn that only asks the player for clarification does not consume game time")
    @pytest.mark.asyncio
    async def test_turn_does_not_increment_on_clarification(self):
        director = make_director(
            route_response=_route("INTERACT", clarify=True, clarify_q="Which door?", delegate=[]),
        )
        await director.act("open door")
        assert director._game_state.turn_count == 0

    @allure.story("Turn counting")
    @allure.title("Every action type in TURN_COUNTING_ACTIONS advances the turn count by one")
    @pytest.mark.asyncio
    async def test_all_counting_actions_increment(self):
        await asyncio.gather(*(_run_action_check(at) for at in TURN_COUNTING_ACTIONS))


@allure.epic("Game Timeline")
@allure.feature("Action routing")
class TestSceneChanges:
    @allure.story("Scene transitions")
    @allure.title("MOVE actions increment the scene number and invoke the SceneBuilder to produce a new scene")
    @pytest.mark.asyncio
    async def test_move_triggers_scene_change(self):
        director = make_director(route_response=_route("MOVE"))
        assert director._game_state.scene_number == 0
        await director.act("go to the market")
        assert director._game_state.scene_number == 1
        director._executor._scene_builder.execute.assert_called_once()

    @allure.story("Scene transitions")
    @allure.title("EXPLORE reuses the current scene so pre-seeded or previously-generated NPCs are not orphaned")
    @pytest.mark.asyncio
    async def test_explore_preserves_current_scene(self):
        """KER-33: LOOK / EXPLORE in the same location+time must not rebuild.

        A rebuild discards the scene's ``SceneNPC`` UUIDs, which cuts
        pre-seeded NPCs off from ``_eligible_npcs`` on subsequent
        turns even though their ``Actor`` and ``NPCCard`` still exist
        in ``game_state``.
        """
        seeded_scene = Scene(
            location_id="forum",
            description="The bustling Roman Forum.",
            npcs_present=[SceneNPC(role="guard", uuid="npc-seeded")],
        )
        gs = make_game_state()
        gs.current_scene = seeded_scene
        director = make_director(game_state=gs, route_response=_route("EXPLORE"))
        await director.act("look around")
        assert gs.scene_number == 0, "EXPLORE must not increment scene_number"
        assert gs.current_scene is seeded_scene, "EXPLORE must not replace the current scene"
        director._executor._scene_builder.execute.assert_not_called()

    @allure.story("Scene transitions")
    @allure.title("EXPLORE on a session with no current scene falls back to building one")
    @pytest.mark.asyncio
    async def test_explore_builds_scene_when_none_exists(self):
        """Fresh-session fallback: when no scene has been built yet, any
        action (including EXPLORE) must materialise one — otherwise the
        turn would narrate into a void.
        """
        gs = make_game_state()
        gs.current_scene = None
        director = make_director(game_state=gs, route_response=_route("EXPLORE"))
        await director.act("explore the area")
        assert gs.scene_number == 1
        director._executor._scene_builder.execute.assert_called_once()

    @allure.story("Scene transitions")
    @allure.title("SLEEP actions trigger a scene change because the player wakes in a new narrative beat")
    @pytest.mark.asyncio
    async def test_sleep_triggers_scene_change(self):
        director = make_director(route_response=_route("SLEEP"))
        await director.act("go to sleep")
        assert director._game_state.scene_number == 1

    @allure.story("Scene transitions")
    @allure.title("TALK actions stay within the current scene and do not re-invoke the SceneBuilder")
    @pytest.mark.asyncio
    async def test_talk_does_not_trigger_scene_change(self):
        director = make_director(route_response=_route(_TALK))
        await director.act("hello")
        assert director._game_state.scene_number == 0
        director._executor._scene_builder.act.assert_not_called()

    @allure.story("Scene transitions")
    @allure.title(
        "A scene change clears the previous scene's conversation log and starts a fresh one for the new scene"
    )
    @pytest.mark.asyncio
    async def test_scene_change_resets_log(self):
        gs = make_game_state()
        gs.scene_conversation_log = [
            {"player_action": "old action", "response_summary": "old", "action_type": _TALK},
        ]
        director = make_director(game_state=gs, route_response=_route("MOVE"))
        await director.act("go north")
        assert len(gs.scene_conversation_log) == 1
        assert gs.scene_conversation_log[0]["player_action"] == "go north"

    @allure.story("Scene transitions")
    @allure.title("EXAMINE actions do not increment the scene number nor invoke the SceneBuilder")
    @pytest.mark.asyncio
    async def test_examine_does_not_trigger_scene_change(self):
        director = make_director(route_response=_route("EXAMINE"))
        await director.act("look around")
        assert director._game_state.scene_number == 0
        director._executor._scene_builder.act.assert_not_called()

    @allure.story("Scene transitions")
    @allure.title("The SCENE_CHANGING_ACTIONS constant contains exactly MOVE and SLEEP")
    @pytest.mark.asyncio
    async def test_scene_changing_actions_constant(self):
        """KER-33: EXPLORE is intentionally excluded — LOOK / EXPLORE do not
        imply a location change or time-of-day shift and must not rebuild the
        scene (that would orphan pre-seeded NPC UUIDs).
        """
        assert SCENE_CHANGING_ACTIONS == {"MOVE", "SLEEP"}

    @allure.story("Scene transitions")
    @allure.title(
        "EXAMINE actions never replace the current scene even when the LLM erroneously delegates to scene_builder"
    )
    @pytest.mark.asyncio
    async def test_examine_with_scene_builder_delegate_does_not_replace_scene(self):
        """Regression: LLM sometimes routes EXAMINE with scene_builder in delegate_to.

        Director must not replace the current scene in that case — only MOVE/SLEEP
        may build a new scene. Otherwise NPCs get regenerated mid-encounter.
        """
        gs = make_game_state()
        original_scene = gs.current_scene
        director = make_director(
            game_state=gs,
            route_response=_route("EXAMINE", delegate=["scene_builder", "narrator"]),
        )
        await director.act("does the guard have a weapon?")
        assert gs.scene_number == 0, "scene_number must not increment on EXAMINE"
        assert gs.current_scene is original_scene, "current_scene must not be replaced"
        director._executor._scene_builder.execute.assert_not_called()


@allure.epic("Game Timeline")
@allure.feature("Action routing")
class TestSceneConversationLog:
    @allure.story("Scene conversation log")
    @allure.title(
        "Each resolved action is appended to the scene conversation log with player action, type, and summary"
    )
    @pytest.mark.asyncio
    async def test_action_appended_to_scene_log(self):
        director = make_director(route_response=_route(_TALK))
        await director.act("hello guard")
        log = director._game_state.scene_conversation_log
        assert len(log) == 1
        assert log[0]["player_action"] == "hello guard"
        assert log[0]["action_type"] == _TALK
        assert "response_summary" in log[0]

    @allure.story("Scene conversation log")
    @allure.title("Multiple actions in the same scene accumulate as separate entries in the conversation log")
    @pytest.mark.asyncio
    async def test_multiple_actions_accumulate(self):
        gs = make_game_state()
        route = _route(_TALK)
        await make_director(game_state=gs, route_response=route).act("hello")
        await make_director(game_state=gs, route_response=route).act("what news?")
        await make_director(game_state=gs, route_response=route).act("examine sword")
        assert len(gs.scene_conversation_log) == 3

    @allure.story("Scene conversation log")
    @allure.title("Long narrator responses are truncated to 500 characters when stored in the scene conversation log")
    @pytest.mark.asyncio
    async def test_response_summary_truncated(self):
        director = make_director(route_response=_route(_TALK), narrator_response="x" * 1000)
        await director.act("say something")
        log_entry = director._game_state.scene_conversation_log[0]
        summary = log_entry["response_summary"]
        assert len(summary) == _SUMMARY_MAX_LENGTH

    @allure.story("Clarification flow")
    @allure.title("Clarification-only turns do not append anything to the scene conversation log")
    @pytest.mark.asyncio
    async def test_clarification_no_scene_log_append(self):
        director = make_director(
            route_response=_route("INTERACT", clarify=True, clarify_q="Which one?", delegate=[]),
        )
        await director.act("take it")
        assert len(director._game_state.scene_conversation_log) == 0
