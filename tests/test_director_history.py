"""Tests for Director scene history, clarification, and call chain delegation."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import allure
import pytest

from llm.message import Role, ToolCall
from tests.director_helpers import make_director, make_game_state, route_plan

_PLAYER_ACTION = "player_action"
_RESPONSE_SUMMARY = "response_summary"
_ACTION_TYPE = "action_type"
_TALK = "TALK"
_INTERACT = "INTERACT"
_ROLE = "role"
_MSG_CONTENT = "content"
_NEEDS_CLARIFICATION = "needs_clarification"
_HISTORY_LOG_SIZE = 15
_EXPECTED_HISTORY_PAIRS = 20


def _interact_tool_call() -> ToolCall:
    """Canonical interact tool call used to drive the clarification follow-up path."""
    return ToolCall(
        name="interact",
        arguments={
            "action_type": "INTERACT",
            "intent": "grab the weapon",
            "delegate_to": ["narrator"],
            "targets": ["guard"],
            "is_aggressive": False,
        },
    )


@allure.epic("Memory & Persistence")
@allure.feature("Scene history & delegation")
class TestSceneHistory:
    @allure.story("Message pair building")
    @allure.title("build_scene_history returns None when the scene conversation log is empty")
    def test_empty_log_returns_none(self):
        director = make_director()
        assert director._router.build_scene_history() is None

    @allure.story("Message pair building")
    @allure.title("Each log entry is rendered as a USER+ASSISTANT message pair for the LLM router")
    def test_returns_message_pairs(self):
        gs = make_game_state()
        gs.scene_conversation_log = [
            {_PLAYER_ACTION: "hello", _RESPONSE_SUMMARY: "Hi there", _ACTION_TYPE: _TALK},
        ]
        director = make_director(game_state=gs)
        history = director._router.build_scene_history()
        assert history is not None
        assert len(history) == 2
        assert history[0].role == Role.USER
        assert "hello" in history[0].body
        assert history[1].role == Role.ASSISTANT

    @allure.story("Message pair building")
    @allure.title("The assistant side of each history pair is valid JSON that parses back to the original action_type")
    def test_assistant_message_is_valid_json(self):
        gs = make_game_state()
        gs.scene_conversation_log = [
            {_PLAYER_ACTION: "hello", _RESPONSE_SUMMARY: "Hi there", _ACTION_TYPE: _TALK},
        ]
        director = make_director(game_state=gs)
        history = director._router.build_scene_history()
        parsed = json.loads(history[1].body)
        assert parsed[_ACTION_TYPE] == _TALK

    @allure.story("Message pair building")
    @allure.title("Scene history sent to the router is capped at the ten most recent entries (twenty messages)")
    def test_caps_at_ten_entries(self):
        gs = make_game_state()
        gs.scene_conversation_log = [
            {_PLAYER_ACTION: f"action-{idx}", _RESPONSE_SUMMARY: f"resp-{idx}", _ACTION_TYPE: _TALK}
            for idx in range(_HISTORY_LOG_SIZE)
        ]
        director = make_director(game_state=gs)
        history = director._router.build_scene_history()
        assert history is not None
        assert len(history) == _EXPECTED_HISTORY_PAIRS
        assert "action-5" in history[0].body

    @allure.story("Scene history summary")
    @allure.title("Director does not inject a scene_history_summary prompt variable when no history exists")
    def test_no_history_no_scene_history_summary(self):
        director = make_director()
        director._ctx.sync_context(director)
        assert "scene_history_summary" not in director._system_prompt_vars

    @allure.story("Scene history summary")
    @allure.title("Director populates scene_history_summary with the recent player actions when history is present")
    def test_with_history_sets_scene_history_summary(self):
        gs = make_game_state()
        gs.scene_conversation_log = [
            {_PLAYER_ACTION: "look around", _ACTION_TYPE: "EXAMINE"},
            {_PLAYER_ACTION: "talk to guard", _ACTION_TYPE: _TALK},
        ]
        director = make_director(game_state=gs)
        director._ctx.sync_context(director)
        summary = director._system_prompt_vars.get("scene_history_summary", "")
        assert "look around" in summary
        assert "talk to guard" in summary

    @allure.story("Scene history summary")
    @allure.title("The scene_history_summary prompt variable contains only the five most recent actions")
    def test_scene_history_summary_caps_at_five(self):
        gs = make_game_state()
        gs.scene_conversation_log = [{_PLAYER_ACTION: f"action-{idx}", _ACTION_TYPE: _TALK} for idx in range(10)]
        director = make_director(game_state=gs)
        director._ctx.sync_context(director)
        summary = director._system_prompt_vars["scene_history_summary"]
        lines = [line for line in summary.split("\n") if line.strip()]
        assert len(lines) == 5
        assert "action-5" in summary
        assert "action-4" not in summary


@allure.epic("Memory & Persistence")
@allure.feature("Scene history & delegation")
class TestClarificationPreservesSceneHistory:
    @allure.story("Clarification follow-up")
    @allure.title("A clarification follow-up prepends prior scene history ahead of the pending clarification turns")
    @pytest.mark.asyncio
    async def test_clarification_followup_with_history(self):
        gs = make_game_state()
        gs.scene_conversation_log = [
            {_PLAYER_ACTION: "punch guard", _RESPONSE_SUMMARY: "Guard blocks.", _ACTION_TYPE: _INTERACT},
        ]
        gs.pending_clarification = [
            {_ROLE: "user", _MSG_CONTENT: 'Player action: "grab his weapon"'},
            {
                _ROLE: "assistant",
                _MSG_CONTENT: json.dumps({"question": "Whose weapon?", "reason": ""}),
            },
        ]
        director = make_director(game_state=gs)
        director._router._send_tool = AsyncMock(return_value=_interact_tool_call())
        await director._router.route_action("the guard")

        call_kwargs = director._router._send_tool.call_args
        conversation_val = call_kwargs.kwargs["conversation"]
        assert len(conversation_val) == 4
        assert conversation_val[0].role == Role.USER
        assert "punch guard" in conversation_val[0].body

    @allure.story("Clarification follow-up")
    @allure.title("A clarification follow-up without prior history sends only the two pending clarification turns")
    @pytest.mark.asyncio
    async def test_clarification_followup_no_history(self):
        gs = make_game_state()
        gs.pending_clarification = [
            {_ROLE: "user", _MSG_CONTENT: 'Player action: "take it"'},
            {
                _ROLE: "assistant",
                _MSG_CONTENT: json.dumps({"question": "Take what?", "reason": ""}),
            },
        ]
        director = make_director(game_state=gs)
        director._router._send_tool = AsyncMock(return_value=_interact_tool_call())
        await director._router.route_action("the sword")

        call_kwargs = director._router._send_tool.call_args
        conversation_val = call_kwargs.kwargs["conversation"]
        assert len(conversation_val) == 2


@allure.epic("Memory & Persistence")
@allure.feature("Scene history & delegation")
class TestDelegation:
    """Director must call sub-agents via execute() for call-chain tracking."""

    @allure.story("Call chain delegation")
    @allure.title("Director delegates to the Narrator via execute() so the call chain is recorded")
    @pytest.mark.asyncio
    async def test_narrator_called_via_execute(self):
        director = make_director(route_response=route_plan("OTHER"))
        await director.act("look around")
        director._executor._narrator.execute.assert_called_once()

    @allure.story("Call chain delegation")
    @allure.title("Director delegates to the SceneBuilder via execute() so the call chain is recorded")
    @pytest.mark.asyncio
    async def test_scene_builder_called_via_execute(self):
        director = make_director(route_response=route_plan("MOVE", delegate=["scene_builder"]))
        await director.act("walk to the ruins")
        director._executor._scene_builder.execute.assert_called_once()

    @allure.story("Call chain delegation")
    @allure.title("Director passes the accumulated scene_history list into the Narrator's execution context")
    @pytest.mark.asyncio
    async def test_narrator_gets_scene_history(self):
        gs = make_game_state()
        gs.scene_conversation_log = [
            {_PLAYER_ACTION: "attack guard", _RESPONSE_SUMMARY: "Guard blocks.", _ACTION_TYPE: _INTERACT},
        ]
        director = make_director(game_state=gs, route_response=route_plan(_INTERACT))
        await director.act("attack again")

        narrator_call = director._executor._narrator.execute.call_args
        context = narrator_call.kwargs.get("context") or narrator_call.args[1]
        assert "scene_history" in context
        assert len(context["scene_history"]) == 1
        assert context["scene_history"][0][_PLAYER_ACTION] == "attack guard"
