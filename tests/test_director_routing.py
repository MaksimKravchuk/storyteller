"""Tests for Director turn counting, scene changes, and conversation log."""

from __future__ import annotations

import asyncio

import pytest

from cast.constants import SCENE_CHANGING_ACTIONS, TURN_COUNTING_ACTIONS
from tests.director_helpers import make_director, make_game_state

_TALK = "TALK"
_SUMMARY_MAX_LENGTH = 500


def _route(action_type, *, clarify=False, clarify_q=None, delegate=("narrator",), targets=()):
    """Build a route_response dict for Director tests."""
    action_plan = {
        "action_type": action_type,
        "targets": list(targets),
        "needs_clarification": clarify,
        "delegate_to": list(delegate) if clarify else delegate,
    }
    if clarify_q:
        action_plan["clarification_question"] = clarify_q
    return action_plan


async def _run_action_check(action_type):
    """Run a single action type and verify turn_count increments."""
    gs = make_game_state()
    director = make_director(game_state=gs, route_response=_route(action_type))
    await director.act("do something")
    assert gs.turn_count == 1, f"{action_type} should increment turn_count"


class TestTurnCounting:
    @pytest.mark.asyncio
    async def test_turn_increments_on_talk(self):
        director = make_director(route_response=_route(_TALK))
        await director.act("talk to someone")
        assert director._deps.game_state.turn_count == 1

    @pytest.mark.asyncio
    async def test_turn_increments_on_interact(self):
        director = make_director(route_response=_route("INTERACT"))
        await director.act("open the door")
        assert director._deps.game_state.turn_count == 1

    @pytest.mark.asyncio
    async def test_turn_does_not_increment_on_examine(self):
        director = make_director(route_response=_route("EXAMINE"))
        await director.act("look at the fountain")
        assert director._deps.game_state.turn_count == 0

    @pytest.mark.asyncio
    async def test_turn_does_not_increment_on_other(self):
        director = make_director(route_response=_route("OTHER"))
        await director.act("hum a tune")
        assert director._deps.game_state.turn_count == 0

    @pytest.mark.asyncio
    async def test_turn_does_not_increment_on_clarification(self):
        director = make_director(
            route_response=_route("INTERACT", clarify=True, clarify_q="Which door?", delegate=[]),
        )
        await director.act("open door")
        assert director._deps.game_state.turn_count == 0

    @pytest.mark.asyncio
    async def test_all_counting_actions_increment(self):
        await asyncio.gather(*(_run_action_check(at) for at in TURN_COUNTING_ACTIONS))


class TestSceneChanges:
    @pytest.mark.asyncio
    async def test_move_triggers_scene_change(self):
        director = make_director(route_response=_route("MOVE"))
        assert director._deps.game_state.scene_number == 0
        await director.act("go to the market")
        assert director._deps.game_state.scene_number == 1
        director._cast.scene_builder.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_explore_triggers_scene_change(self):
        director = make_director(route_response=_route("EXPLORE"))
        await director.act("explore the area")
        assert director._deps.game_state.scene_number == 1

    @pytest.mark.asyncio
    async def test_sleep_triggers_scene_change(self):
        director = make_director(route_response=_route("SLEEP"))
        await director.act("go to sleep")
        assert director._deps.game_state.scene_number == 1

    @pytest.mark.asyncio
    async def test_talk_does_not_trigger_scene_change(self):
        director = make_director(route_response=_route(_TALK))
        await director.act("hello")
        assert director._deps.game_state.scene_number == 0
        director._cast.scene_builder.act.assert_not_called()

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

    @pytest.mark.asyncio
    async def test_examine_does_not_trigger_scene_change(self):
        director = make_director(route_response=_route("EXAMINE"))
        await director.act("look around")
        assert director._deps.game_state.scene_number == 0
        director._cast.scene_builder.act.assert_not_called()

    @pytest.mark.asyncio
    async def test_scene_changing_actions_constant(self):
        assert SCENE_CHANGING_ACTIONS == {"EXPLORE", "MOVE", "SLEEP"}

    @pytest.mark.asyncio
    async def test_examine_with_scene_builder_delegate_does_not_replace_scene(self):
        """Regression: LLM sometimes routes EXAMINE with scene_builder in delegate_to.

        Director must not replace the current scene in that case — only MOVE/EXPLORE/SLEEP
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
        director._cast.scene_builder.execute.assert_not_called()


class TestSceneConversationLog:
    @pytest.mark.asyncio
    async def test_action_appended_to_scene_log(self):
        director = make_director(route_response=_route(_TALK))
        await director.act("hello guard")
        log = director._deps.game_state.scene_conversation_log
        assert len(log) == 1
        assert log[0]["player_action"] == "hello guard"
        assert log[0]["action_type"] == _TALK
        assert "response_summary" in log[0]

    @pytest.mark.asyncio
    async def test_multiple_actions_accumulate(self):
        gs = make_game_state()
        route = _route(_TALK)
        await make_director(game_state=gs, route_response=route).act("hello")
        await make_director(game_state=gs, route_response=route).act("what news?")
        await make_director(game_state=gs, route_response=route).act("examine sword")
        assert len(gs.scene_conversation_log) == 3

    @pytest.mark.asyncio
    async def test_response_summary_truncated(self):
        director = make_director(route_response=_route(_TALK), narrator_response="x" * 1000)
        await director.act("say something")
        log_entry = director._deps.game_state.scene_conversation_log[0]
        summary = log_entry["response_summary"]
        assert len(summary) == _SUMMARY_MAX_LENGTH

    @pytest.mark.asyncio
    async def test_clarification_no_scene_log_append(self):
        director = make_director(
            route_response=_route("INTERACT", clarify=True, clarify_q="Which one?", delegate=[]),
        )
        await director.act("take it")
        assert len(director._deps.game_state.scene_conversation_log) == 0
