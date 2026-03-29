"""Tests for Director turn/scene logic and Actor mood extraction."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from cast.actor import Actor, _extract_mood as _actor_extract_mood
from cast.director import (
    Director,
    SCENE_CHANGING_ACTIONS,
    TURN_COUNTING_ACTIONS,
)
from knowledge.graph import KnowledgeGraph
from knowledge.memory import MemoryManager
from knowledge.query import KnowledgeQueryEngine
from llm.message import Role
from models.game_state import GameState
from models.npc_card import NPCCard
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

    # Mock agents — wire both .act and .execute so Director can call
    # .execute() while tests can still inspect call args on either.
    scene_result = Scene(
        location_id="new-loc",
        description="A new place.",
        npcs_present=[SceneNPC(role="merchant")],
    )
    scene_builder = AsyncMock()
    scene_builder.act = AsyncMock(return_value=scene_result)
    scene_builder.execute = AsyncMock(return_value=scene_result)

    narrator = AsyncMock()
    narrator.act = AsyncMock(return_value=narrator_response)
    narrator.execute = AsyncMock(return_value=narrator_response)

    npc_generator = AsyncMock()
    npc_generator.act = AsyncMock(return_value=[])
    npc_generator.execute = AsyncMock(return_value=[])

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
        director._send_json = AsyncMock(return_value=route_response)  # type: ignore[method-assign]

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
        assert not gs.scene_conversation_log


# ---------------------------------------------------------------------------
# Turn counting
# ---------------------------------------------------------------------------


class TestTurnCounting:
    @pytest.mark.asyncio
    async def test_turn_increments_on_talk(self):
        director = _make_director(
            route_response={
                "action_type": "TALK",
                "targets": [],
                "needs_clarification": False,
                "delegate_to": ["narrator"],
            }
        )
        await director.act("talk to someone")
        assert director.game_state.turn_count == 1

    @pytest.mark.asyncio
    async def test_turn_increments_on_interact(self):
        director = _make_director(
            route_response={
                "action_type": "INTERACT",
                "targets": [],
                "needs_clarification": False,
                "delegate_to": ["narrator"],
            }
        )
        await director.act("open the door")
        assert director.game_state.turn_count == 1

    @pytest.mark.asyncio
    async def test_turn_does_not_increment_on_examine(self):
        director = _make_director(
            route_response={
                "action_type": "EXAMINE",
                "targets": [],
                "needs_clarification": False,
                "delegate_to": ["narrator"],
            }
        )
        await director.act("look at the fountain")
        assert director.game_state.turn_count == 0

    @pytest.mark.asyncio
    async def test_turn_does_not_increment_on_other(self):
        director = _make_director(
            route_response={
                "action_type": "OTHER",
                "targets": [],
                "needs_clarification": False,
                "delegate_to": ["narrator"],
            }
        )
        await director.act("wait")
        assert director.game_state.turn_count == 0

    @pytest.mark.asyncio
    async def test_turn_does_not_increment_on_clarification(self):
        director = _make_director(
            route_response={
                "action_type": "INTERACT",
                "targets": [],
                "needs_clarification": True,
                "clarification_question": "Which door?",
                "delegate_to": [],
            }
        )
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
        director = _make_director(
            route_response={
                "action_type": "MOVE",
                "targets": [],
                "needs_clarification": False,
                "delegate_to": ["narrator"],
            }
        )
        assert director.game_state.scene_number == 0
        await director.act("go to the market")
        assert director.game_state.scene_number == 1
        director.scene_builder.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_explore_triggers_scene_change(self):
        director = _make_director(
            route_response={
                "action_type": "EXPLORE",
                "targets": [],
                "needs_clarification": False,
                "delegate_to": ["narrator"],
            }
        )
        await director.act("explore the area")
        assert director.game_state.scene_number == 1
        director.scene_builder.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_sleep_triggers_scene_change(self):
        director = _make_director(
            route_response={
                "action_type": "SLEEP",
                "targets": [],
                "needs_clarification": False,
                "delegate_to": ["narrator"],
            }
        )
        await director.act("go to sleep")
        assert director.game_state.scene_number == 1
        director.scene_builder.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_talk_does_not_trigger_scene_change(self):
        director = _make_director(
            route_response={
                "action_type": "TALK",
                "targets": [],
                "needs_clarification": False,
                "delegate_to": ["narrator"],
            }
        )
        await director.act("hello")
        assert director.game_state.scene_number == 0
        director.scene_builder.act.assert_not_called()

    @pytest.mark.asyncio
    async def test_examine_does_not_trigger_scene_change(self):
        director = _make_director(
            route_response={
                "action_type": "EXAMINE",
                "targets": [],
                "needs_clarification": False,
                "delegate_to": ["narrator"],
            }
        )
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
        director = _make_director(
            route_response={
                "action_type": "TALK",
                "targets": [],
                "needs_clarification": False,
                "delegate_to": ["narrator"],
            }
        )
        await director.act("hello guard")
        log = director.game_state.scene_conversation_log
        assert len(log) == 1
        assert log[0]["player_action"] == "hello guard"
        assert log[0]["action_type"] == "TALK"
        assert "response_summary" in log[0]

    @pytest.mark.asyncio
    async def test_multiple_actions_accumulate(self):
        gs = _make_game_state()

        for action_text in ("hello", "what news?", "examine sword"):
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
        director = _make_director(
            route_response={
                "action_type": "INTERACT",
                "targets": [],
                "needs_clarification": True,
                "clarification_question": "Which one?",
                "delegate_to": [],
            }
        )
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
            {"player_action": f"action-{idx}", "response_summary": f"resp-{idx}", "action_type": "TALK"}
            for idx in range(15)
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
        gs.scene_conversation_log = [{"player_action": f"action-{idx}", "action_type": "TALK"} for idx in range(10)]
        director = _make_director(game_state=gs)
        director._sync_context_from_state()
        summary = director._system_prompt_vars["scene_history_summary"]
        lines = [line for line in summary.split("\n") if line.strip()]
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
            {
                "role": "assistant",
                "content": json.dumps(
                    {
                        "needs_clarification": True,
                        "clarification_question": "Whose weapon?",
                    }
                ),
            },
        ]
        director = _make_director(game_state=gs)
        # Mock _send_json to capture the conversation kwarg
        director._send_json = AsyncMock(
            return_value={
                "action_type": "INTERACT",
                "targets": ["guard"],
                "needs_clarification": False,
                "delegate_to": ["narrator"],
            }
        )

        await director._route_action("the guard")

        call_kwargs = director._send_json.call_args
        conversation = (
            call_kwargs.kwargs.get("conversation") or call_kwargs.args[1]
            if len(call_kwargs.args) > 1
            else call_kwargs.kwargs["conversation"]
        )

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
            {
                "role": "assistant",
                "content": json.dumps(
                    {
                        "needs_clarification": True,
                        "clarification_question": "Take what?",
                    }
                ),
            },
        ]
        director = _make_director(game_state=gs)
        director._send_json = AsyncMock(
            return_value={
                "action_type": "INTERACT",
                "targets": [],
                "needs_clarification": False,
                "delegate_to": ["narrator"],
            }
        )

        await director._route_action("the sword")

        call_kwargs = director._send_json.call_args
        conversation = (
            call_kwargs.kwargs.get("conversation") or call_kwargs.args[1]
            if len(call_kwargs.args) > 1
            else call_kwargs.kwargs["conversation"]
        )

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

        narrator_call = director.narrator.execute.call_args
        context = narrator_call.kwargs.get("context") or narrator_call.args[1]
        assert "scene_history" in context
        assert len(context["scene_history"]) == 1
        assert context["scene_history"][0]["player_action"] == "attack guard"


# ---------------------------------------------------------------------------
# Call chain delegation
# ---------------------------------------------------------------------------


class TestCallChainDelegation:
    """Director must call sub-agents via execute() for call-chain tracking."""

    @pytest.mark.asyncio
    async def test_narrator_called_via_execute(self):
        director = _make_director(
            route_response={
                "action_type": "OTHER",
                "targets": [],
                "needs_clarification": False,
                "delegate_to": ["narrator"],
            }
        )
        await director.act("look around")

        # Narrator.execute() should have been called (not just .act())
        director.narrator.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_scene_builder_called_via_execute(self):
        director = _make_director(
            route_response={
                "action_type": "EXPLORE",
                "targets": [],
                "needs_clarification": False,
                "delegate_to": ["scene_builder"],
            }
        )
        await director.act("explore the ruins")

        director.scene_builder.execute.assert_called_once()


# ---------------------------------------------------------------------------
# Actor._extract_mood
# ---------------------------------------------------------------------------


class TestExtractMood:
    def test_no_mood_tag(self):
        text, mood = _actor_extract_mood("*draws his sword* — Stand back!")
        assert text == "*draws his sword* — Stand back!"
        assert mood is None

    def test_mood_tag_at_end(self):
        text, mood = _actor_extract_mood("*lunges at you with a spear*\n[MOOD: hostile]")
        assert text == "*lunges at you with a spear*"
        assert mood == "hostile"

    def test_mood_tag_uppercase_normalised(self):
        text, mood = _actor_extract_mood("Back off!\n[MOOD: ENRAGED]")
        assert mood == "enraged"

    def test_mood_tag_with_extra_space_before_word(self):
        text, mood = _actor_extract_mood("Help!\n[MOOD:  terrified]")
        assert mood == "terrified"

    def test_mood_tag_not_at_end_is_ignored(self):
        text, mood = _actor_extract_mood("[MOOD: hostile]\nI will destroy you!")
        assert mood is None
        assert "[MOOD: hostile]" in text

    def test_empty_string(self):
        text, mood = _actor_extract_mood("")
        assert text == ""
        assert mood is None


# ---------------------------------------------------------------------------
# Actor mood update integration
# ---------------------------------------------------------------------------


class TestActorMoodUpdate:
    @pytest.mark.asyncio
    async def test_mood_updated_after_response(self):
        npc = NPCCard(
            name="Guard",
            occupation="city guard",
            personality_traits=["aggressive"],
            speech_style="curt, military",
        )
        assert npc.current_mood == "neutral"

        kg = KnowledgeGraph()
        kq = KnowledgeQueryEngine(kg)
        llm_client = AsyncMock()

        actor = Actor(llm_client=llm_client, npc=npc, knowledge_query=kq)
        # Mock _send to return text with mood tag
        actor._send = AsyncMock(return_value="*tackles you to the ground*\n[MOOD: hostile]")

        actor_response = await actor.act("attack guard", {"location_name": "forum"})
        assert npc.current_mood == "hostile"
        assert "[MOOD:" not in actor_response

    @pytest.mark.asyncio
    async def test_mood_unchanged_when_no_tag(self):
        npc = NPCCard(
            name="Merchant",
            occupation="merchant",
            personality_traits=["friendly"],
            speech_style="cheerful",
        )
        kg = KnowledgeGraph()
        kq = KnowledgeQueryEngine(kg)
        llm_client = AsyncMock()

        actor = Actor(llm_client=llm_client, npc=npc, knowledge_query=kq)
        actor._send = AsyncMock(return_value="Welcome, friend!")

        await actor.act("hello", {"location_name": "market"})
        assert npc.current_mood == "neutral"

    @pytest.mark.asyncio
    async def test_conversation_history_excludes_mood_tag(self):
        npc = NPCCard(name="Guard", occupation="guard")
        kg = KnowledgeGraph()
        kq = KnowledgeQueryEngine(kg)
        llm_client = AsyncMock()

        actor = Actor(llm_client=llm_client, npc=npc, knowledge_query=kq)
        actor._send = AsyncMock(return_value="*blocks your strike*\n[MOOD: hostile]")

        await actor.act("punch guard", {"location_name": "gate"})
        # The mood tag should be stripped from conversation history
        assert len(actor._conversation) == 2
        assert "[MOOD:" not in actor._conversation[1].content


# ---------------------------------------------------------------------------
# Combat dice integration in Director
# ---------------------------------------------------------------------------


class TestCombatDiceIntegration:
    @pytest.mark.asyncio
    async def test_aggressive_action_injects_dice_roll(self):
        director, mock_actor = self._make_director_with_npc(is_aggressive=True)
        await director.act("punch the guard")

        # Actor should have been called with dice roll in input
        call_args = mock_actor.execute.call_args
        input_text = call_args.kwargs.get("input_data") or call_args.args[0]
        assert "[DICE ROLL:" in input_text
        assert "OUTCOME:" in input_text

    @pytest.mark.asyncio
    async def test_non_aggressive_action_no_dice_roll(self):
        director, mock_actor = self._make_director_with_npc(is_aggressive=False)
        await director.act("talk to the guard")

        call_args = mock_actor.execute.call_args
        input_text = call_args.kwargs.get("input_data") or call_args.args[0]
        assert "[DICE ROLL:" not in input_text

    @pytest.mark.asyncio
    async def test_combat_roll_included_in_dialogue_result(self):
        director, mock_actor = self._make_director_with_npc(is_aggressive=True)
        await director.act("attack guard")

        # Check that narrator received combat_roll in the dialogue data
        narrator_call = director.narrator.execute.call_args
        raw_input = narrator_call.kwargs.get("input_data") or narrator_call.args[0]
        dialogue = raw_input.get("dialogue", [])
        assert len(dialogue) == 1
        assert "combat_roll" in dialogue[0]

    @pytest.mark.asyncio
    async def test_npc_without_combat_skill_uses_default(self):
        """NPC with no combat_skill attribute defaults to 3."""
        gs = _make_game_state()
        npc = NPCCard(name="Merchant", occupation="merchant")
        npc.uuid = "npc-1"
        gs.npcs["npc-1"] = npc

        director = _make_director(
            game_state=gs,
            route_response={
                "action_type": "INTERACT",
                "is_aggressive": True,
                "targets": ["merchant"],
                "needs_clarification": False,
                "delegate_to": ["actor", "narrator"],
            },
        )
        mock_actor = AsyncMock()
        mock_actor.act = AsyncMock(return_value="*cowers*")
        mock_actor.execute = AsyncMock(return_value="*cowers*")
        director.actors["npc-1"] = mock_actor

        await director.act("punch the merchant")

        call_args = mock_actor.execute.call_args
        input_text = call_args.kwargs.get("input_data") or call_args.args[0]
        # Default combat_skill=3, so bonus should be +3
        assert "+3]" in input_text

    def _make_director_with_npc(self, is_aggressive: bool, combat_skill: int = 5) -> tuple[Director, AsyncMock]:
        """Create a Director with a registered NPC and mock Actor."""
        gs = _make_game_state()
        npc = NPCCard(
            name="Guard",
            occupation="city guard",
            attributes={"combat_skill": combat_skill},
        )
        npc.uuid = "npc-1"  # match the SceneNPC uuid
        gs.npcs["npc-1"] = npc

        director = _make_director(
            game_state=gs,
            route_response={
                "action_type": "INTERACT",
                "is_aggressive": is_aggressive,
                "targets": ["guard"],
                "needs_clarification": False,
                "delegate_to": ["actor", "narrator"],
            },
        )

        # Create a mock actor — wire both .act and .execute
        mock_actor = AsyncMock()
        mock_actor.act = AsyncMock(return_value="*fights back*")
        mock_actor.execute = AsyncMock(return_value="*fights back*")
        director.actors["npc-1"] = mock_actor

        return director, mock_actor


# ---------------------------------------------------------------------------
# NPC retaliation after mood change
# ---------------------------------------------------------------------------


class TestNPCRetaliation:
    @pytest.mark.asyncio
    async def test_retaliation_on_mood_change_to_hostile(self):
        """When NPC mood changes to hostile and dice pass, NPC retaliates."""
        gs = _make_game_state()
        npc = NPCCard(
            name="Guard",
            occupation="city guard",
            attributes={"combat_skill": 7},
        )
        npc.uuid = "npc-1"
        npc.current_mood = "neutral"
        gs.npcs["npc-1"] = npc

        director = _make_director(
            game_state=gs,
            route_response={
                "action_type": "INTERACT",
                "is_aggressive": True,
                "targets": ["guard"],
                "needs_clarification": False,
                "delegate_to": ["actor", "narrator"],
            },
        )

        call_count = [0]

        async def mock_act(input_data, context):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call: player attacks, NPC mood changes
                npc.current_mood = "hostile"
                return "*blocks the strike*\n[MOOD: hostile]"
            else:
                # Second call: retaliation
                return "*swings sword at you*"

        mock_actor = AsyncMock()
        mock_actor.act = AsyncMock(side_effect=mock_act)
        mock_actor.execute = AsyncMock(side_effect=mock_act)
        director.actors["npc-1"] = mock_actor

        # Patch roll_aggression to always trigger
        from cast import director as director_module

        original_roll = director_module.roll_aggression

        def always_attacks(mood, _rng=None):
            from cast.dice import AggressionRoll

            return AggressionRoll(will_attack=True, roll=15, threshold=5, mood=mood)

        director_module.roll_aggression = always_attacks
        try:
            await director.act("attack the guard")
        finally:
            director_module.roll_aggression = original_roll

        # Actor should have been called twice: once for attack, once for retaliation
        assert mock_actor.execute.call_count == 2
        second_call = mock_actor.execute.call_args_list[1]
        input_text = second_call.kwargs.get("input_data") or second_call.args[0]
        assert "retaliates" in input_text
        assert "[DICE ROLL:" in input_text

    @pytest.mark.asyncio
    async def test_no_retaliation_when_mood_unchanged(self):
        """No retaliation if mood doesn't change."""
        gs = _make_game_state()
        npc = NPCCard(name="Guard", occupation="guard")
        npc.uuid = "npc-1"
        npc.current_mood = "neutral"
        gs.npcs["npc-1"] = npc

        director = _make_director(
            game_state=gs,
            route_response={
                "action_type": "TALK",
                "targets": ["guard"],
                "needs_clarification": False,
                "delegate_to": ["actor", "narrator"],
            },
        )

        mock_actor = AsyncMock()
        mock_actor.act = AsyncMock(return_value="Hello there.")
        mock_actor.execute = AsyncMock(return_value="Hello there.")
        director.actors["npc-1"] = mock_actor

        await director.act("greet the guard")

        # Actor should only be called once (no retaliation)
        assert mock_actor.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_no_retaliation_when_dice_fail(self):
        """Mood changes but dice don't pass → no retaliation."""
        gs = _make_game_state()
        npc = NPCCard(name="Guard", occupation="guard")
        npc.uuid = "npc-1"
        npc.current_mood = "neutral"
        gs.npcs["npc-1"] = npc

        director = _make_director(
            game_state=gs,
            route_response={
                "action_type": "INTERACT",
                "is_aggressive": True,
                "targets": ["guard"],
                "needs_clarification": False,
                "delegate_to": ["actor", "narrator"],
            },
        )

        async def mock_act(input_data, context):
            npc.current_mood = "hostile"
            return "*shoves you back*"

        mock_actor = AsyncMock()
        mock_actor.act = AsyncMock(side_effect=mock_act)
        mock_actor.execute = AsyncMock(side_effect=mock_act)
        director.actors["npc-1"] = mock_actor

        # Patch roll_aggression to never trigger
        from cast import director as director_module

        original_roll = director_module.roll_aggression

        def never_attacks(mood, _rng=None):
            from cast.dice import AggressionRoll

            return AggressionRoll(will_attack=False, roll=2, threshold=5, mood=mood)

        director_module.roll_aggression = never_attacks
        try:
            await director.act("punch the guard")
        finally:
            director_module.roll_aggression = original_roll

        # Only one call — no retaliation
        assert mock_actor.execute.call_count == 1


# ---------------------------------------------------------------------------
# Duplicate NPC name deduplication
# ---------------------------------------------------------------------------


class TestDuplicateNPCNames:
    @pytest.mark.asyncio
    async def test_duplicate_npc_names_only_one_actor_called(self):
        """When multiple NPCs share the same name, only one Actor is called."""
        gs = _make_game_state()

        # Two NPCs with the same name but different UUIDs
        npc1 = NPCCard(name="Guard", occupation="night guard")
        npc1.uuid = "npc-1"
        gs.npcs["npc-1"] = npc1

        npc2 = NPCCard(name="Guard", occupation="dock guard")
        npc2.uuid = "npc-2"
        gs.npcs["npc-2"] = npc2

        gs.current_scene = Scene(
            location_id="docks",
            description="The docks.",
            npcs_present=[
                SceneNPC(role="night guard", uuid="npc-1"),
                SceneNPC(role="dock guard", uuid="npc-2"),
            ],
        )

        director = _make_director(
            game_state=gs,
            route_response={
                "action_type": "TALK",
                "targets": ["guard"],
                "needs_clarification": False,
                "delegate_to": ["actor", "narrator"],
            },
        )

        mock_actor1 = AsyncMock()
        mock_actor1.execute = AsyncMock(return_value="Hello.")
        mock_actor2 = AsyncMock()
        mock_actor2.execute = AsyncMock(return_value="Hi there.")
        director.actors["npc-1"] = mock_actor1
        director.actors["npc-2"] = mock_actor2

        await director.act("talk to the guard")

        # Only ONE actor should be called, not both
        total_calls = mock_actor1.execute.call_count + mock_actor2.execute.call_count
        assert total_calls == 1

    @pytest.mark.asyncio
    async def test_retaliation_skips_duplicate_names(self):
        """When multiple same-name NPCs change mood, only one retaliates."""
        gs = _make_game_state()

        npc1 = NPCCard(
            name="Guard",
            occupation="night guard",
            attributes={"combat_skill": 5},
        )
        npc1.uuid = "npc-1"
        npc1.current_mood = "neutral"
        gs.npcs["npc-1"] = npc1

        npc2 = NPCCard(
            name="Guard",
            occupation="dock guard",
            attributes={"combat_skill": 5},
        )
        npc2.uuid = "npc-2"
        npc2.current_mood = "neutral"
        gs.npcs["npc-2"] = npc2

        gs.current_scene = Scene(
            location_id="docks",
            description="The docks.",
            npcs_present=[
                SceneNPC(role="night guard", uuid="npc-1"),
                SceneNPC(role="dock guard", uuid="npc-2"),
            ],
        )

        director = _make_director(
            game_state=gs,
            route_response={
                "action_type": "INTERACT",
                "is_aggressive": True,
                "targets": ["guard"],
                "needs_clarification": False,
                "delegate_to": ["actor", "narrator"],
            },
        )

        call_count = [0]

        async def mock_act(input_data, context):
            call_count[0] += 1
            # Both NPCs become hostile after the attack
            npc1.current_mood = "hostile"
            npc2.current_mood = "hostile"
            return "*blocks*\n[MOOD: hostile]"

        mock_actor1 = AsyncMock()
        mock_actor1.execute = AsyncMock(side_effect=mock_act)
        mock_actor2 = AsyncMock()
        mock_actor2.execute = AsyncMock(side_effect=mock_act)
        director.actors["npc-1"] = mock_actor1
        director.actors["npc-2"] = mock_actor2

        # Patch roll_aggression to always trigger
        from cast import director as director_module

        original_roll = director_module.roll_aggression

        def always_attacks(mood, _rng=None):
            from cast.dice import AggressionRoll

            return AggressionRoll(will_attack=True, roll=15, threshold=5, mood=mood)

        director_module.roll_aggression = always_attacks
        try:
            await director.act("attack the guard")
        finally:
            director_module.roll_aggression = original_roll

        # 1 dialogue call + 1 retaliation = 2 total (not 2+2=4)
        total_calls = mock_actor1.execute.call_count + mock_actor2.execute.call_count
        assert total_calls == 2
