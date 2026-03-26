"""Tests for Director turn/scene logic."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from cast.director import (
    Director,
    SCENE_CHANGING_ACTIONS,
    TURN_COUNTING_ACTIONS,
)
from knowledge.graph import KnowledgeGraph
from knowledge.memory import MemoryManager
from llm.message import Message, Role
from models.game_state import GameState
from models.scene import Scene, SceneNPC
from models.setting import Setting
from timeline.event_manager import EventManager


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_setting() -> Setting:
    return Setting(
        name="Ancient Rome",
        time_period="1st century AD",
        region="Italy",
        summary="The Roman Empire.",
    )


def _make_game_state() -> GameState:
    kg = KnowledgeGraph()
    gs = GameState(setting=_make_setting(), knowledge_graph=kg)
    gs.current_scene = Scene(
        location_id="forum",
        description="The bustling Roman Forum.",
        npcs_present=[SceneNPC(role="guard", uuid="npc-1")],
        points_of_interest=["fountain", "statue"],
    )
    return gs


def _make_director(
    game_state: GameState | None = None,
    route_response: dict | None = None,
    narrator_response: str = "Narrated result.",
) -> Director:
    """Create a Director with mocked LLM and agents."""
    gs = game_state or _make_game_state()

    # Mock LLM client — _send_json returns the routing plan
    llm_client = AsyncMock()

    # Mock agents
    scene_builder = AsyncMock()
    scene_builder.act = AsyncMock(return_value=Scene(
        location_id="new-loc",
        description="A new place.",
        npcs_present=[SceneNPC(role="merchant")],
    ))

    narrator = AsyncMock()
    narrator.act = AsyncMock(return_value=narrator_response)

    npc_generator = AsyncMock()
    npc_generator.act = AsyncMock(return_value=[])

    data_miner = AsyncMock()

    event_manager = EventManager(game_state=gs, knowledge_graph=gs.knowledge_graph)
    memory_manager = MagicMock(spec=MemoryManager)

    director = Director(
        llm_client=llm_client,
        game_state=gs,
        event_manager=event_manager,
        memory_manager=memory_manager,
        scene_builder=scene_builder,
        narrator=narrator,
        npc_generator=npc_generator,
        data_miner=data_miner,
        language="English",
    )

    # Patch _send_json to return the desired routing response
    if route_response:
        director._send_json = AsyncMock(return_value=route_response)

    return director


# ---------------------------------------------------------------------------
# GameState new fields
# ---------------------------------------------------------------------------


class TestGameStateSceneFields:
    def test_initial_scene_number(self):
        gs = _make_game_state()
        assert gs.scene_number == 0

    def test_initial_scene_conversation_log(self):
        gs = _make_game_state()
        assert gs.scene_conversation_log == []


# ---------------------------------------------------------------------------
# Turn counting
# ---------------------------------------------------------------------------


class TestTurnCounting:
    @pytest.mark.asyncio
    async def test_turn_increments_on_talk(self):
        director = _make_director(route_response={
            "action_type": "TALK",
            "targets": [],
            "needs_clarification": False,
            "delegate_to": ["narrator"],
        })
        await director.act("talk to someone")
        assert director.game_state.turn_count == 1

    @pytest.mark.asyncio
    async def test_turn_increments_on_interact(self):
        director = _make_director(route_response={
            "action_type": "INTERACT",
            "targets": [],
            "needs_clarification": False,
            "delegate_to": ["narrator"],
        })
        await director.act("open the door")
        assert director.game_state.turn_count == 1

    @pytest.mark.asyncio
    async def test_turn_does_not_increment_on_examine(self):
        director = _make_director(route_response={
            "action_type": "EXAMINE",
            "targets": [],
            "needs_clarification": False,
            "delegate_to": ["narrator"],
        })
        await director.act("look at the fountain")
        assert director.game_state.turn_count == 0

    @pytest.mark.asyncio
    async def test_turn_does_not_increment_on_other(self):
        director = _make_director(route_response={
            "action_type": "OTHER",
            "targets": [],
            "needs_clarification": False,
            "delegate_to": ["narrator"],
        })
        await director.act("wait")
        assert director.game_state.turn_count == 0

    @pytest.mark.asyncio
    async def test_turn_does_not_increment_on_clarification(self):
        director = _make_director(route_response={
            "action_type": "INTERACT",
            "targets": [],
            "needs_clarification": True,
            "clarification_question": "Which door?",
            "delegate_to": [],
        })
        await director.act("open door")
        assert director.game_state.turn_count == 0

    @pytest.mark.asyncio
    async def test_all_counting_actions_increment(self):
        """Verify every action in TURN_COUNTING_ACTIONS increments turn_count."""
        for action_type in TURN_COUNTING_ACTIONS:
            gs = _make_game_state()
            director = _make_director(
                game_state=gs,
                route_response={
                    "action_type": action_type,
                    "targets": [],
                    "needs_clarification": False,
                    "delegate_to": ["narrator"],
                },
            )
            await director.act("do something")
            assert gs.turn_count == 1, f"{action_type} should increment turn_count"


# ---------------------------------------------------------------------------
# Scene changes
# ---------------------------------------------------------------------------


class TestSceneChanges:
    @pytest.mark.asyncio
    async def test_move_triggers_scene_change(self):
        director = _make_director(route_response={
            "action_type": "MOVE",
            "targets": [],
            "needs_clarification": False,
            "delegate_to": ["narrator"],
        })
        assert director.game_state.scene_number == 0
        await director.act("go to the market")
        assert director.game_state.scene_number == 1
        director.scene_builder.act.assert_called_once()

    @pytest.mark.asyncio
    async def test_explore_triggers_scene_change(self):
        director = _make_director(route_response={
            "action_type": "EXPLORE",
            "targets": [],
            "needs_clarification": False,
            "delegate_to": ["narrator"],
        })
        await director.act("explore the area")
        assert director.game_state.scene_number == 1
        director.scene_builder.act.assert_called_once()

    @pytest.mark.asyncio
    async def test_sleep_triggers_scene_change(self):
        director = _make_director(route_response={
            "action_type": "SLEEP",
            "targets": [],
            "needs_clarification": False,
            "delegate_to": ["narrator"],
        })
        await director.act("go to sleep")
        assert director.game_state.scene_number == 1
        director.scene_builder.act.assert_called_once()

    @pytest.mark.asyncio
    async def test_talk_does_not_trigger_scene_change(self):
        director = _make_director(route_response={
            "action_type": "TALK",
            "targets": [],
            "needs_clarification": False,
            "delegate_to": ["narrator"],
        })
        await director.act("hello")
        assert director.game_state.scene_number == 0
        director.scene_builder.act.assert_not_called()

    @pytest.mark.asyncio
    async def test_examine_does_not_trigger_scene_change(self):
        director = _make_director(route_response={
            "action_type": "EXAMINE",
            "targets": [],
            "needs_clarification": False,
            "delegate_to": ["narrator"],
        })
        await director.act("look around")
        assert director.game_state.scene_number == 0
        director.scene_builder.act.assert_not_called()

    @pytest.mark.asyncio
    async def test_scene_change_resets_scene_conversation_log(self):
        gs = _make_game_state()
        gs.scene_conversation_log = [
            {"player_action": "old action", "response_summary": "old", "action_type": "TALK"},
        ]
        director = _make_director(
            game_state=gs,
            route_response={
                "action_type": "MOVE",
                "targets": [],
                "needs_clarification": False,
                "delegate_to": ["narrator"],
            },
        )
        await director.act("go north")
        # Scene log was reset, then the new action was appended
        assert len(gs.scene_conversation_log) == 1
        assert gs.scene_conversation_log[0]["player_action"] == "go north"

    @pytest.mark.asyncio
    async def test_scene_changing_actions_constant(self):
        """SCENE_CHANGING_ACTIONS should include EXPLORE, MOVE, SLEEP."""
        assert SCENE_CHANGING_ACTIONS == {"EXPLORE", "MOVE", "SLEEP"}


# ---------------------------------------------------------------------------
# Scene conversation log
# ---------------------------------------------------------------------------


class TestSceneConversationLog:
    @pytest.mark.asyncio
    async def test_action_appended_to_scene_log(self):
        director = _make_director(route_response={
            "action_type": "TALK",
            "targets": [],
            "needs_clarification": False,
            "delegate_to": ["narrator"],
        })
        await director.act("hello guard")
        log = director.game_state.scene_conversation_log
        assert len(log) == 1
        assert log[0]["player_action"] == "hello guard"
        assert log[0]["action_type"] == "TALK"
        assert "response_summary" in log[0]

    @pytest.mark.asyncio
    async def test_multiple_actions_accumulate(self):
        gs = _make_game_state()

        for action_text in ["hello", "what news?", "examine sword"]:
            director = _make_director(
                game_state=gs,
                route_response={
                    "action_type": "TALK",
                    "targets": [],
                    "needs_clarification": False,
                    "delegate_to": ["narrator"],
                },
            )
            await director.act(action_text)

        assert len(gs.scene_conversation_log) == 3
        assert gs.scene_conversation_log[0]["player_action"] == "hello"
        assert gs.scene_conversation_log[2]["player_action"] == "examine sword"

    @pytest.mark.asyncio
    async def test_response_summary_truncated(self):
        long_response = "x" * 1000
        director = _make_director(
            route_response={
                "action_type": "TALK",
                "targets": [],
                "needs_clarification": False,
                "delegate_to": ["narrator"],
            },
            narrator_response=long_response,
        )
        await director.act("say something")
        summary = director.game_state.scene_conversation_log[0]["response_summary"]
        assert len(summary) == 500

    @pytest.mark.asyncio
    async def test_clarification_does_not_append_to_scene_log(self):
        director = _make_director(route_response={
            "action_type": "INTERACT",
            "targets": [],
            "needs_clarification": True,
            "clarification_question": "Which one?",
            "delegate_to": [],
        })
        await director.act("take it")
        assert len(director.game_state.scene_conversation_log) == 0


# ---------------------------------------------------------------------------
# Scene history for LLM context
# ---------------------------------------------------------------------------


class TestBuildSceneHistory:
    def test_empty_log_returns_none(self):
        director = _make_director()
        assert director._build_scene_history() is None

    def test_returns_message_pairs(self):
        gs = _make_game_state()
        gs.scene_conversation_log = [
            {"player_action": "hello", "response_summary": "Hi there", "action_type": "TALK"},
        ]
        director = _make_director(game_state=gs)
        history = director._build_scene_history()
        assert history is not None
        assert len(history) == 2
        assert history[0].role == Role.USER
        assert "hello" in history[0].content
        assert history[1].role == Role.ASSISTANT
        # Assistant message should be valid JSON
        parsed = json.loads(history[1].content)
        assert parsed["action_type"] == "TALK"

    def test_caps_at_10_entries(self):
        gs = _make_game_state()
        gs.scene_conversation_log = [
            {"player_action": f"action-{i}", "response_summary": f"resp-{i}", "action_type": "TALK"}
            for i in range(15)
        ]
        director = _make_director(game_state=gs)
        history = director._build_scene_history()
        assert history is not None
        # 10 entries × 2 messages each = 20 messages
        assert len(history) == 20
        # Should be the last 10, starting from action-5
        assert "action-5" in history[0].content


# ---------------------------------------------------------------------------
# System prompt scene history
# ---------------------------------------------------------------------------


class TestSyncContextSceneHistory:
    def test_no_history_no_scene_history_summary(self):
        director = _make_director()
        director._sync_context_from_state()
        # scene_history_summary should not be set (section will be skipped)
        assert "scene_history_summary" not in director._system_prompt_vars

    def test_with_history_sets_scene_history_summary(self):
        gs = _make_game_state()
        gs.scene_conversation_log = [
            {"player_action": "look around", "action_type": "EXAMINE"},
            {"player_action": "talk to guard", "action_type": "TALK"},
        ]
        director = _make_director(game_state=gs)
        director._sync_context_from_state()
        summary = director._system_prompt_vars.get("scene_history_summary", "")
        assert "look around" in summary
        assert "talk to guard" in summary
        assert "EXAMINE" in summary
        assert "TALK" in summary

    def test_scene_history_summary_caps_at_5(self):
        gs = _make_game_state()
        gs.scene_conversation_log = [
            {"player_action": f"action-{i}", "action_type": "TALK"}
            for i in range(10)
        ]
        director = _make_director(game_state=gs)
        director._sync_context_from_state()
        summary = director._system_prompt_vars["scene_history_summary"]
        lines = [l for l in summary.split("\n") if l.strip()]
        assert len(lines) == 5
        # Should be last 5: action-5 through action-9
        assert "action-5" in summary
        assert "action-4" not in summary


# ---------------------------------------------------------------------------
# Clarification preserves scene history
# ---------------------------------------------------------------------------


class TestClarificationPreservesSceneHistory:
    @pytest.mark.asyncio
    async def test_clarification_followup_includes_scene_history(self):
        """When resolving a clarification, scene history should be
        prepended before the clarification exchange so the LLM retains
        context (e.g. an ongoing fight)."""
        gs = _make_game_state()
        gs.scene_conversation_log = [
            {"player_action": "punch guard", "response_summary": "Guard blocks.", "action_type": "INTERACT"},
        ]
        # Simulate a pending clarification (saved from prior turn)
        gs.pending_clarification = [
            {"role": "user", "content": 'Player action: "grab his weapon"'},
            {"role": "assistant", "content": json.dumps({
                "needs_clarification": True,
                "clarification_question": "Whose weapon?",
            })},
        ]
        director = _make_director(game_state=gs)
        # Mock _send_json to capture the conversation kwarg
        director._send_json = AsyncMock(return_value={
            "action_type": "INTERACT",
            "targets": ["guard"],
            "needs_clarification": False,
            "delegate_to": ["narrator"],
        })

        await director._route_action("the guard")

        call_kwargs = director._send_json.call_args
        conversation = call_kwargs.kwargs.get("conversation") or call_kwargs.args[1] if len(call_kwargs.args) > 1 else call_kwargs.kwargs["conversation"]

        # Should have: 2 scene history messages + 2 clarification messages = 4
        assert len(conversation) == 4
        # First pair is scene history
        assert conversation[0].role == Role.USER
        assert "punch guard" in conversation[0].content
        # Last pair is clarification
        assert conversation[2].role == Role.USER
        assert "grab his weapon" in conversation[2].content

    @pytest.mark.asyncio
    async def test_clarification_followup_without_scene_history(self):
        """Clarification on first turn of a scene (empty scene log)
        should still work — just the clarification messages."""
        gs = _make_game_state()
        gs.pending_clarification = [
            {"role": "user", "content": 'Player action: "take it"'},
            {"role": "assistant", "content": json.dumps({
                "needs_clarification": True,
                "clarification_question": "Take what?",
            })},
        ]
        director = _make_director(game_state=gs)
        director._send_json = AsyncMock(return_value={
            "action_type": "INTERACT",
            "targets": [],
            "needs_clarification": False,
            "delegate_to": ["narrator"],
        })

        await director._route_action("the sword")

        call_kwargs = director._send_json.call_args
        conversation = call_kwargs.kwargs.get("conversation") or call_kwargs.args[1] if len(call_kwargs.args) > 1 else call_kwargs.kwargs["conversation"]

        # Only clarification messages, no scene history
        assert len(conversation) == 2

    @pytest.mark.asyncio
    async def test_narrator_receives_scene_history_in_context(self):
        """The narrator should receive scene_history in its context dict."""
        gs = _make_game_state()
        gs.scene_conversation_log = [
            {"player_action": "attack guard", "response_summary": "Guard blocks.", "action_type": "INTERACT"},
        ]
        director = _make_director(
            game_state=gs,
            route_response={
                "action_type": "INTERACT",
                "targets": [],
                "needs_clarification": False,
                "delegate_to": ["narrator"],
            },
        )
        await director.act("attack again")

        narrator_call = director.narrator.act.call_args
        context = narrator_call.kwargs.get("context") or narrator_call.args[1]
        assert "scene_history" in context
        assert len(context["scene_history"]) == 1
        assert context["scene_history"][0]["player_action"] == "attack guard"
