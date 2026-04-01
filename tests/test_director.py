"""Tests for Director turn/scene logic and Actor mood extraction."""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from cast.actor import Actor, _extract_mood as _actor_extract_mood
from cast.director import (
    Director,
    DirectorCast,
    DirectorDeps,
    SCENE_CHANGING_ACTIONS,
    TURN_COUNTING_ACTIONS,
)
from knowledge.graph import KnowledgeGraph
from knowledge.memory import MemoryManager
from knowledge.query import KnowledgeQueryEngine
from llm.message import LLMResponse, Role
from models.game_state import GameState
from models.npc_card import NPCCard
from models.scene import Scene, SceneNPC
from models.setting import Setting
from timeline.event_manager import EventManager

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_GUARD = "guard"
_NPC_A = "npc-1"
_MERCHANT = "merchant"
_ACTION_TYPE = "action_type"
_TALK = "TALK"
_TARGETS = "targets"
_NEEDS_CLARIFICATION = "needs_clarification"
_DELEGATE_TO = "delegate_to"
_NARRATOR = "narrator"
_INTERACT = "INTERACT"
_EXAMINE = "EXAMINE"
_CLARIFICATION_QUESTION = "clarification_question"
_HELLO = "hello"
_LOOK_AROUND = "look around"
_PLAYER_ACTION = "player_action"
_RESPONSE_SUMMARY = "response_summary"
_SUMMARY_MAX_LEN = 500
_SCENE_LOG_FEED_SIZE = 15
_SCENE_MSG_COUNT = 20
_HOSTILE = "hostile"
_ATTACK_GUARD = "attack guard"
_CITY_GUARD = "city guard"
_GUARD_NAME = "Guard"
_NEUTRAL = "neutral"
_MERCHANT_NAME = "Merchant"
_INPUT_DATA = "input_data"
_IS_AGGRESSIVE = "is_aggressive"
_ACTOR = "actor"
_COMBAT_SKILL = "combat_skill"
_ROLL_FIFTEEN = 15
_UUID_A = "uuid-1"
_UUID_B = "uuid-2"
_NPC_B = "npc-2"
_NIGHT_GUARD = "night guard"
_DOCK_GUARD = "dock guard"
_ROLE = "role"
_MSG_CONTENT = "content"
_CONVERSATION = "conversation"


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
        npcs_present=[SceneNPC(role=_GUARD, uuid=_NPC_A)],
        points_of_interest=["fountain", "statue"],
    )
    return gs


def _make_mock_agent(return_value: object = None) -> AsyncMock:
    """Create a mock agent with both .act and .execute wired."""
    mock = AsyncMock()
    mock.act = AsyncMock(return_value=return_value)
    mock.execute = AsyncMock(return_value=return_value)
    return mock


def _make_cast(narrator_response: str = "Narrated result.") -> DirectorCast:
    """Build a DirectorCast with mocked agents."""
    return DirectorCast(
        scene_builder=_make_mock_agent(
            Scene(
                location_id="new-loc",
                description="A new place.",
                npcs_present=[SceneNPC(role=_MERCHANT)],
            )
        ),
        narrator=_make_mock_agent(narrator_response),
        npc_generator=_make_mock_agent([]),
        data_miner=AsyncMock(),
    )


def _make_director(
    game_state: GameState | None = None,
    route_response: dict | None = None,
    narrator_response: str = "Narrated result.",
) -> Director:
    """Create a Director with mocked LLM and agents."""
    gs = game_state or _make_game_state()

    director = Director(
        llm_client=AsyncMock(),
        deps=DirectorDeps(
            game_state=gs,
            event_manager=EventManager(game_state=gs, knowledge_graph=gs.knowledge_graph),
            memory_manager=MagicMock(spec=MemoryManager),
        ),
        cast=_make_cast(narrator_response),
        language="English",
    )

    if route_response:
        director._send_json = AsyncMock(return_value=route_response)  # type: ignore[method-assign]

    return director


def _make_actor_with_npc(
    npc_name: str = _GUARD_NAME,
    occupation: str = _CITY_GUARD,
    **npc_kwargs: Any,
) -> tuple[Actor, NPCCard]:
    """Create a mocked Actor + NPCCard pair for tests."""
    npc = NPCCard(name=npc_name, occupation=occupation, **npc_kwargs)
    actor = Actor(
        llm_client=AsyncMock(),
        npc=npc,
        knowledge_query=KnowledgeQueryEngine(KnowledgeGraph()),
    )
    return actor, npc


class _RetaliationMockAct:
    """Mock act that changes NPC mood on first call."""

    def __init__(self, npc, call_count):
        self._npc = npc
        self._call_count = call_count

    def __call__(self, input_data, context):
        self._call_count[0] += 1
        if self._call_count[0] == 1:
            self._npc.current_mood = _HOSTILE
            return "*blocks the strike*\n[MOOD: {0}]".format(_HOSTILE)
        return "*retaliates fiercely*\n[MOOD: {0}]".format(_HOSTILE)


class _SimpleMockAct:
    """Mock act that sets NPC mood and returns a fixed string."""

    def __init__(self, npc, mood):
        self._npc = npc
        self._mood = mood

    def __call__(self, input_data, context):
        self._npc.current_mood = self._mood
        return "*shoves you back*"


class _DualMoodMockAct:
    """Mock act that changes mood on both NPCs."""

    def __init__(self, npc1, npc2, call_count):
        self._npc1 = npc1
        self._npc2 = npc2
        self._call_count = call_count

    def __call__(self, input_data, context):
        self._call_count[0] += 1
        self._npc1.current_mood = _HOSTILE
        self._npc2.current_mood = _HOSTILE
        return "*blocks*\n[MOOD: {0}]".format(_HOSTILE)


class _AlwaysAttacks:
    """roll_aggression replacement that always triggers attack."""

    def __call__(self, mood, _rng=None):
        from cast.dice import AggressionRoll

        return AggressionRoll(will_attack=True, roll=_ROLL_FIFTEEN, threshold=5, mood=mood)


class _NeverAttacks:
    """roll_aggression replacement that never triggers attack."""

    def __call__(self, mood, _rng=None):
        from cast.dice import AggressionRoll

        return AggressionRoll(will_attack=False, roll=2, threshold=5, mood=mood)


class _FixedCombat:
    """roll_combat replacement with fixed outcome."""

    def __call__(self, combat_skill, _rng=None):
        from cast.dice import CombatOutcome, CombatRoll

        return CombatRoll(
            outcome=CombatOutcome.NPC_OVERPOWERS,
            npc_roll=_ROLL_FIFTEEN,
            player_roll=5,
            npc_bonus=combat_skill,
        )


def _make_retaliation_actor(npc: NPCCard) -> AsyncMock:
    """Create a mock actor wired with _RetaliationMockAct side effect."""
    call_count = [0]
    side_effect = _RetaliationMockAct(npc, call_count)
    mock_actor = AsyncMock()
    mock_actor.act = AsyncMock(side_effect=side_effect)
    mock_actor.execute = AsyncMock(side_effect=side_effect)
    return mock_actor


async def _run_with_patched_aggression(
    replacement: Any,
    coro: Any,
    combat_replacement: Any = None,
) -> Any:
    """Run a coroutine with roll_aggression (and optionally roll_combat) patched."""
    from cast import director as director_module

    original_roll = director_module.roll_aggression
    original_combat = director_module.roll_combat if combat_replacement else None
    director_module.roll_aggression = replacement  # type: ignore[assignment]
    if combat_replacement:
        director_module.roll_combat = combat_replacement  # type: ignore[assignment]
    try:
        return await coro
    except Exception:
        raise
    finally:
        director_module.roll_aggression = original_roll
        if combat_replacement:
            director_module.roll_combat = original_combat  # type: ignore[assignment]


def _extract_execute_input(mock_actor: AsyncMock, call_index: int = 0) -> str:
    """Extract the input_data string from a mock actor's execute call."""
    call = mock_actor.execute.call_args_list[call_index]
    return call.kwargs.get(_INPUT_DATA) or call.args[0]


def _setup_npc_in_game_state(
    gs: GameState,
    uuid: str,
    name: str = _GUARD_NAME,
    occupation: str = _CITY_GUARD,
    mood: str = _NEUTRAL,
    **kwargs: Any,
) -> NPCCard:
    """Create an NPC, assign it a uuid and mood, and register it in game state."""
    npc = NPCCard(name=name, occupation=occupation, **kwargs)
    npc.uuid = uuid
    npc.current_mood = mood
    gs.npcs[uuid] = npc
    return npc


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


async def _assert_action_increments_turn(action_type: str) -> None:
    """Helper: verify a single action type increments turn_count."""
    gs = _make_game_state()
    director = _make_director(
        game_state=gs,
        route_response={
            _ACTION_TYPE: action_type,
            _TARGETS: [],
            _NEEDS_CLARIFICATION: False,
            _DELEGATE_TO: [_NARRATOR],
        },
    )
    await director.act("do something")
    assert gs.turn_count == 1, f"{action_type} should increment turn_count"


class TestTurnCounting:
    @pytest.mark.asyncio
    async def test_turn_increments_on_talk(self):
        director = _make_director(
            route_response={
                _ACTION_TYPE: _TALK,
                _TARGETS: [],
                _NEEDS_CLARIFICATION: False,
                _DELEGATE_TO: [_NARRATOR],
            }
        )
        await director.act("talk to someone")
        assert director.game_state.turn_count == 1

    @pytest.mark.asyncio
    async def test_turn_increments_on_interact(self):
        director = _make_director(
            route_response={
                _ACTION_TYPE: _INTERACT,
                _TARGETS: [],
                _NEEDS_CLARIFICATION: False,
                _DELEGATE_TO: [_NARRATOR],
            }
        )
        await director.act("open the door")
        assert director.game_state.turn_count == 1

    @pytest.mark.asyncio
    async def test_turn_does_not_increment_on_examine(self):
        director = _make_director(
            route_response={
                _ACTION_TYPE: _EXAMINE,
                _TARGETS: [],
                _NEEDS_CLARIFICATION: False,
                _DELEGATE_TO: [_NARRATOR],
            }
        )
        await director.act("look at the fountain")
        assert director.game_state.turn_count == 0

    @pytest.mark.asyncio
    async def test_turn_does_not_increment_on_other(self):
        director = _make_director(
            route_response={
                _ACTION_TYPE: "OTHER",
                _TARGETS: [],
                _NEEDS_CLARIFICATION: False,
                _DELEGATE_TO: [_NARRATOR],
            }
        )
        await director.act("wait")
        assert director.game_state.turn_count == 0

    @pytest.mark.asyncio
    async def test_turn_does_not_increment_on_clarification(self):
        director = _make_director(
            route_response={
                _ACTION_TYPE: _INTERACT,
                _TARGETS: [],
                _NEEDS_CLARIFICATION: True,
                _CLARIFICATION_QUESTION: "Which door?",
                _DELEGATE_TO: [],
            }
        )
        await director.act("open door")
        assert director.game_state.turn_count == 0

    @pytest.mark.asyncio
    async def test_all_counting_actions_increment(self):
        """Verify every action in TURN_COUNTING_ACTIONS increments turn_count."""
        await asyncio.gather(*(_assert_action_increments_turn(at) for at in TURN_COUNTING_ACTIONS))


# ---------------------------------------------------------------------------
# Scene changes
# ---------------------------------------------------------------------------


class TestSceneChanges:
    @pytest.mark.asyncio
    async def test_move_triggers_scene_change(self):
        director = _make_director(
            route_response={
                _ACTION_TYPE: "MOVE",
                _TARGETS: [],
                _NEEDS_CLARIFICATION: False,
                _DELEGATE_TO: [_NARRATOR],
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
                _ACTION_TYPE: "EXPLORE",
                _TARGETS: [],
                _NEEDS_CLARIFICATION: False,
                _DELEGATE_TO: [_NARRATOR],
            }
        )
        await director.act("explore the area")
        assert director.game_state.scene_number == 1
        director.scene_builder.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_sleep_triggers_scene_change(self):
        director = _make_director(
            route_response={
                _ACTION_TYPE: "SLEEP",
                _TARGETS: [],
                _NEEDS_CLARIFICATION: False,
                _DELEGATE_TO: [_NARRATOR],
            }
        )
        await director.act("go to sleep")
        assert director.game_state.scene_number == 1
        director.scene_builder.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_talk_does_not_trigger_scene_change(self):
        director = _make_director(
            route_response={
                _ACTION_TYPE: _TALK,
                _TARGETS: [],
                _NEEDS_CLARIFICATION: False,
                _DELEGATE_TO: [_NARRATOR],
            }
        )
        await director.act(_HELLO)
        assert director.game_state.scene_number == 0
        director.scene_builder.act.assert_not_called()

    @pytest.mark.asyncio
    async def test_examine_does_not_trigger_scene_change(self):
        director = _make_director(
            route_response={
                _ACTION_TYPE: _EXAMINE,
                _TARGETS: [],
                _NEEDS_CLARIFICATION: False,
                _DELEGATE_TO: [_NARRATOR],
            }
        )
        await director.act(_LOOK_AROUND)
        assert director.game_state.scene_number == 0
        director.scene_builder.act.assert_not_called()

    @pytest.mark.asyncio
    async def test_scene_change_resets_log(self):
        gs = _make_game_state()
        gs.scene_conversation_log = [
            {_PLAYER_ACTION: "old action", _RESPONSE_SUMMARY: "old", _ACTION_TYPE: _TALK},
        ]
        director = _make_director(
            game_state=gs,
            route_response={
                _ACTION_TYPE: "MOVE",
                _TARGETS: [],
                _NEEDS_CLARIFICATION: False,
                _DELEGATE_TO: [_NARRATOR],
            },
        )
        await director.act("go north")
        # Scene log was reset, then the new action was appended
        assert len(gs.scene_conversation_log) == 1
        assert gs.scene_conversation_log[0][_PLAYER_ACTION] == "go north"

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
                _ACTION_TYPE: _TALK,
                _TARGETS: [],
                _NEEDS_CLARIFICATION: False,
                _DELEGATE_TO: [_NARRATOR],
            }
        )
        await director.act("hello guard")
        log = director.game_state.scene_conversation_log
        assert len(log) == 1
        assert log[0][_PLAYER_ACTION] == "hello guard"
        assert log[0][_ACTION_TYPE] == _TALK
        assert _RESPONSE_SUMMARY in log[0]

    @pytest.mark.asyncio
    async def test_multiple_actions_accumulate(self):
        gs = _make_game_state()
        route = {
            _ACTION_TYPE: _TALK,
            _TARGETS: [],
            _NEEDS_CLARIFICATION: False,
            _DELEGATE_TO: [_NARRATOR],
        }

        await _make_director(game_state=gs, route_response=route).act(_HELLO)
        await _make_director(game_state=gs, route_response=route).act("what news?")
        await _make_director(game_state=gs, route_response=route).act("examine sword")

        assert len(gs.scene_conversation_log) == 3
        assert gs.scene_conversation_log[0][_PLAYER_ACTION] == _HELLO
        assert gs.scene_conversation_log[2][_PLAYER_ACTION] == "examine sword"

    @pytest.mark.asyncio
    async def test_response_summary_truncated(self):
        long_response = "x" * 1000
        director = _make_director(
            route_response={
                _ACTION_TYPE: _TALK,
                _TARGETS: [],
                _NEEDS_CLARIFICATION: False,
                _DELEGATE_TO: [_NARRATOR],
            },
            narrator_response=long_response,
        )
        await director.act("say something")
        summary = director.game_state.scene_conversation_log[0][_RESPONSE_SUMMARY]
        assert len(summary) == _SUMMARY_MAX_LEN

    @pytest.mark.asyncio
    async def test_clarification_no_scene_log_append(self):
        director = _make_director(
            route_response={
                _ACTION_TYPE: _INTERACT,
                _TARGETS: [],
                _NEEDS_CLARIFICATION: True,
                _CLARIFICATION_QUESTION: "Which one?",
                _DELEGATE_TO: [],
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
            {_PLAYER_ACTION: _HELLO, _RESPONSE_SUMMARY: "Hi there", _ACTION_TYPE: _TALK},
        ]
        director = _make_director(game_state=gs)
        history = director._build_scene_history()
        assert history is not None
        assert len(history) == 2
        assert history[0].role == Role.USER
        assert _HELLO in history[0].content
        assert history[1].role == Role.ASSISTANT

    def test_assistant_message_is_valid_json(self):
        gs = _make_game_state()
        gs.scene_conversation_log = [
            {_PLAYER_ACTION: _HELLO, _RESPONSE_SUMMARY: "Hi there", _ACTION_TYPE: _TALK},
        ]
        director = _make_director(game_state=gs)
        history = director._build_scene_history()
        parsed = json.loads(history[1].content)
        assert parsed[_ACTION_TYPE] == _TALK

    def test_caps_at_ten_entries(self):
        gs = _make_game_state()
        gs.scene_conversation_log = [
            {_PLAYER_ACTION: f"action-{idx}", _RESPONSE_SUMMARY: f"resp-{idx}", _ACTION_TYPE: _TALK}
            for idx in range(_SCENE_LOG_FEED_SIZE)
        ]
        director = _make_director(game_state=gs)
        history = director._build_scene_history()
        assert history is not None
        # 10 entries × 2 messages each = 20 messages
        assert len(history) == _SCENE_MSG_COUNT
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
            {_PLAYER_ACTION: _LOOK_AROUND, _ACTION_TYPE: "EXAMINE"},
            {_PLAYER_ACTION: "talk to guard", _ACTION_TYPE: _TALK},
        ]
        director = _make_director(game_state=gs)
        director._sync_context_from_state()
        summary = director._system_prompt_vars.get("scene_history_summary", "")
        assert "look around" in summary
        assert "talk to guard" in summary
        assert "EXAMINE" in summary
        assert "TALK" in summary

    def test_scene_history_summary_caps_at_five(self):
        gs = _make_game_state()
        gs.scene_conversation_log = [{_PLAYER_ACTION: f"action-{idx}", _ACTION_TYPE: _TALK} for idx in range(10)]
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
    async def test_clarification_followup_with_history(self):
        """When resolving a clarification, scene history should be
        prepended before the clarification exchange so the LLM retains
        context (e.g. an ongoing fight)."""
        gs = _make_game_state()
        gs.scene_conversation_log = [
            {_PLAYER_ACTION: "punch guard", _RESPONSE_SUMMARY: "Guard blocks.", _ACTION_TYPE: _INTERACT},
        ]
        # Simulate a pending clarification (saved from prior turn)
        gs.pending_clarification = [
            {_ROLE: "user", _MSG_CONTENT: 'Player action: "grab his weapon"'},
            {
                _ROLE: "assistant",
                _MSG_CONTENT: json.dumps(
                    {
                        _NEEDS_CLARIFICATION: True,
                        _CLARIFICATION_QUESTION: "Whose weapon?",
                    }
                ),
            },
        ]
        director = _make_director(game_state=gs)
        # Mock _send_json to capture the conversation kwarg
        director._send_json = AsyncMock(
            return_value={
                _ACTION_TYPE: _INTERACT,
                _TARGETS: [_GUARD],
                _NEEDS_CLARIFICATION: False,
                _DELEGATE_TO: [_NARRATOR],
            }
        )

        await director._route_action("the guard")

        call_kwargs = director._send_json.call_args
        conversation = (
            call_kwargs.kwargs.get(_CONVERSATION) or call_kwargs.args[1]
            if len(call_kwargs.args) > 1
            else call_kwargs.kwargs[_CONVERSATION]
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
    async def test_clarification_followup_no_history(self):
        """Clarification on first turn of a scene (empty scene log)
        should still work — just the clarification messages."""
        gs = _make_game_state()
        gs.pending_clarification = [
            {_ROLE: "user", _MSG_CONTENT: 'Player action: "take it"'},
            {
                _ROLE: "assistant",
                _MSG_CONTENT: json.dumps(
                    {
                        _NEEDS_CLARIFICATION: True,
                        _CLARIFICATION_QUESTION: "Take what?",
                    }
                ),
            },
        ]
        director = _make_director(game_state=gs)
        director._send_json = AsyncMock(
            return_value={
                _ACTION_TYPE: _INTERACT,
                _TARGETS: [],
                _NEEDS_CLARIFICATION: False,
                _DELEGATE_TO: [_NARRATOR],
            }
        )

        await director._route_action("the sword")

        call_kwargs = director._send_json.call_args
        conversation = (
            call_kwargs.kwargs.get(_CONVERSATION) or call_kwargs.args[1]
            if len(call_kwargs.args) > 1
            else call_kwargs.kwargs[_CONVERSATION]
        )

        # Only clarification messages, no scene history
        assert len(conversation) == 2

    @pytest.mark.asyncio
    async def test_narrator_gets_scene_history(self):
        """The narrator should receive scene_history in its context dict."""
        gs = _make_game_state()
        gs.scene_conversation_log = [
            {_PLAYER_ACTION: _ATTACK_GUARD, _RESPONSE_SUMMARY: "Guard blocks.", _ACTION_TYPE: _INTERACT},
        ]
        director = _make_director(
            game_state=gs,
            route_response={
                _ACTION_TYPE: _INTERACT,
                _TARGETS: [],
                _NEEDS_CLARIFICATION: False,
                _DELEGATE_TO: [_NARRATOR],
            },
        )
        await director.act("attack again")

        narrator_call = director.narrator.execute.call_args
        context = narrator_call.kwargs.get("context") or narrator_call.args[1]
        assert "scene_history" in context
        assert len(context["scene_history"]) == 1
        assert context["scene_history"][0][_PLAYER_ACTION] == _ATTACK_GUARD


# ---------------------------------------------------------------------------
# Call chain delegation
# ---------------------------------------------------------------------------


class TestCallChainDelegation:
    """Director must call sub-agents via execute() for call-chain tracking."""

    @pytest.mark.asyncio
    async def test_narrator_called_via_execute(self):
        director = _make_director(
            route_response={
                _ACTION_TYPE: "OTHER",
                _TARGETS: [],
                _NEEDS_CLARIFICATION: False,
                _DELEGATE_TO: [_NARRATOR],
            }
        )
        await director.act(_LOOK_AROUND)

        # Narrator.execute() should have been called (not just .act())
        director.narrator.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_scene_builder_called_via_execute(self):
        director = _make_director(
            route_response={
                _ACTION_TYPE: "EXPLORE",
                _TARGETS: [],
                _NEEDS_CLARIFICATION: False,
                _DELEGATE_TO: ["scene_builder"],
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
        text, mood = _actor_extract_mood(f"*lunges at you with a spear*\n[MOOD: {_HOSTILE}]")
        assert text == "*lunges at you with a spear*"
        assert mood == _HOSTILE

    def test_mood_tag_uppercase_normalised(self):
        text, mood = _actor_extract_mood("Back off!\n[MOOD: ENRAGED]")
        assert mood == "enraged"

    def test_mood_tag_with_extra_space_before_word(self):
        text, mood = _actor_extract_mood("Help!\n[MOOD:  terrified]")
        assert mood == "terrified"

    def test_mood_tag_not_at_end_is_ignored(self):
        text, mood = _actor_extract_mood(f"[MOOD: {_HOSTILE}]\nI will destroy you!")
        assert mood is None
        assert f"[MOOD: {_HOSTILE}]" in text

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
        actor, npc = _make_actor_with_npc(
            personality_traits=["aggressive"],
            speech_style="curt, military",
        )
        assert npc.current_mood == _NEUTRAL

        actor._send = AsyncMock(return_value=f"*tackles you to the ground*\n[MOOD: {_HOSTILE}]")

        actor_response = await actor.act(_ATTACK_GUARD, {"location_name": "forum"})
        assert npc.current_mood == _HOSTILE
        assert "[MOOD:" not in actor_response

    @pytest.mark.asyncio
    async def test_mood_unchanged_when_no_tag(self):
        actor, npc = _make_actor_with_npc(
            npc_name=_MERCHANT_NAME,
            occupation=_MERCHANT,
            personality_traits=["friendly"],
            speech_style="cheerful",
        )
        actor._send = AsyncMock(return_value="Welcome, friend!")

        await actor.act(_HELLO, {"location_name": "market"})
        assert npc.current_mood == _NEUTRAL

    @pytest.mark.asyncio
    async def test_conversation_history_excludes_mood_tag(self):
        npc = NPCCard(name=_GUARD_NAME, occupation=_GUARD)
        kg = KnowledgeGraph()
        kq = KnowledgeQueryEngine(kg)
        llm_client = AsyncMock()

        actor = Actor(llm_client=llm_client, npc=npc, knowledge_query=kq)
        actor._send = AsyncMock(return_value=f"*blocks your strike*\n[MOOD: {_HOSTILE}]")

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
        input_text = call_args.kwargs.get(_INPUT_DATA) or call_args.args[0]
        assert "[DICE ROLL:" in input_text
        assert "OUTCOME:" in input_text

    @pytest.mark.asyncio
    async def test_non_aggressive_action_no_dice_roll(self):
        director, mock_actor = self._make_director_with_npc(is_aggressive=False)
        await director.act("talk to the guard")

        call_args = mock_actor.execute.call_args
        input_text = call_args.kwargs.get(_INPUT_DATA) or call_args.args[0]
        assert "[DICE ROLL:" not in input_text

    @pytest.mark.asyncio
    async def test_combat_roll_included_in_dialogue_result(self):
        director, mock_actor = self._make_director_with_npc(is_aggressive=True)
        await director.act(_ATTACK_GUARD)

        # Check that narrator received combat_roll in the dialogue data
        narrator_call = director.narrator.execute.call_args
        raw_input = narrator_call.kwargs.get(_INPUT_DATA) or narrator_call.args[0]
        dialogue = raw_input.get("dialogue", [])
        assert len(dialogue) == 1
        assert "combat_roll" in dialogue[0]

    @pytest.mark.asyncio
    async def test_npc_without_combat_skill_uses_default(self):
        """NPC with no combat_skill attribute defaults to 3."""
        director, mock_actor = self._make_director_with_npc(is_aggressive=True, combat_skill=0)

        # Re-register NPC without combat_skill attribute to test default
        npc = NPCCard(name=_MERCHANT_NAME, occupation=_MERCHANT)
        npc.uuid = _NPC_A
        director.game_state.npcs[_NPC_A] = npc
        mock_actor = _make_mock_agent("*cowers*")
        director.actors[_NPC_A] = mock_actor

        await director.act("punch the merchant")

        call_args = mock_actor.execute.call_args
        input_text = call_args.kwargs.get(_INPUT_DATA) or call_args.args[0]
        assert "+3]" in input_text

    def _make_director_with_npc(self, is_aggressive: bool, combat_skill: int = 5) -> tuple[Director, AsyncMock]:
        """Create a Director with a registered NPC and mock Actor."""
        gs = _make_game_state()
        npc = NPCCard(
            name=_GUARD_NAME,
            occupation=_CITY_GUARD,
            attributes={_COMBAT_SKILL: combat_skill},
        )
        npc.uuid = _NPC_A  # match the SceneNPC uuid
        gs.npcs[_NPC_A] = npc

        director = _make_director(
            game_state=gs,
            route_response={
                _ACTION_TYPE: _INTERACT,
                _IS_AGGRESSIVE: is_aggressive,
                _TARGETS: [_GUARD],
                _NEEDS_CLARIFICATION: False,
                _DELEGATE_TO: [_ACTOR, _NARRATOR],
            },
        )

        # Create a mock actor — wire both .act and .execute
        mock_actor = AsyncMock()
        mock_actor.act = AsyncMock(return_value="*fights back*")
        mock_actor.execute = AsyncMock(return_value="*fights back*")
        director.actors[_NPC_A] = mock_actor

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
            name=_GUARD_NAME,
            occupation=_CITY_GUARD,
            attributes={_COMBAT_SKILL: 7},
        )
        npc.uuid = _NPC_A
        npc.current_mood = _NEUTRAL
        gs.npcs[_NPC_A] = npc

        director = _make_director(
            game_state=gs,
            route_response={
                _ACTION_TYPE: _INTERACT,
                _IS_AGGRESSIVE: True,
                _TARGETS: [_GUARD],
                _NEEDS_CLARIFICATION: False,
                _DELEGATE_TO: [_ACTOR, _NARRATOR],
            },
        )

        director.actors[_NPC_A] = _make_retaliation_actor(npc)

        # Patch roll_aggression to always trigger
        await _run_with_patched_aggression(
            _AlwaysAttacks(),
            director.act("attack the guard"),
        )

        # Actor should have been called twice: once for attack, once for retaliation
        assert director.actors[_NPC_A].execute.call_count == 2
        input_text = _extract_execute_input(director.actors[_NPC_A], call_index=1)
        assert "retaliates" in input_text
        assert "[DICE ROLL:" in input_text

    @pytest.mark.asyncio
    async def test_no_retaliation_when_mood_unchanged(self):
        """No retaliation if mood doesn't change."""
        gs = _make_game_state()
        npc = NPCCard(name=_GUARD_NAME, occupation=_GUARD)
        npc.uuid = _NPC_A
        npc.current_mood = _NEUTRAL
        gs.npcs[_NPC_A] = npc

        director = _make_director(
            game_state=gs,
            route_response={
                _ACTION_TYPE: _TALK,
                _TARGETS: [_GUARD],
                _NEEDS_CLARIFICATION: False,
                _DELEGATE_TO: [_ACTOR, _NARRATOR],
            },
        )

        mock_actor = AsyncMock()
        mock_actor.act = AsyncMock(return_value="Hello there.")
        mock_actor.execute = AsyncMock(return_value="Hello there.")
        director.actors[_NPC_A] = mock_actor

        await director.act("greet the guard")

        # Actor should only be called once (no retaliation)
        assert mock_actor.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_no_retaliation_when_dice_fail(self):
        """Mood changes but dice don't pass → no retaliation."""
        gs = _make_game_state()
        npc = _setup_npc_in_game_state(gs, _NPC_A, name=_GUARD_NAME, occupation=_GUARD)

        director = _make_director(
            game_state=gs,
            route_response={
                _ACTION_TYPE: _INTERACT,
                _IS_AGGRESSIVE: True,
                _TARGETS: [_GUARD],
                _NEEDS_CLARIFICATION: False,
                _DELEGATE_TO: [_ACTOR, _NARRATOR],
            },
        )

        side_effect = _SimpleMockAct(npc, _HOSTILE)
        director.actors[_NPC_A] = _make_mock_agent(None)
        director.actors[_NPC_A].act = AsyncMock(side_effect=side_effect)
        director.actors[_NPC_A].execute = AsyncMock(side_effect=side_effect)

        await _run_with_patched_aggression(
            _NeverAttacks(),
            director.act("punch the guard"),
        )

        # Only one call — no retaliation
        assert director.actors[_NPC_A].execute.call_count == 1

    @pytest.mark.asyncio
    async def test_retaliation_deduplication_by_name(self):
        """Two actor entries for NPCs with the same name produce only one retaliation."""
        gs = _make_game_state()
        _setup_npc_in_game_state(gs, _UUID_A, name="Bandit", occupation="bandit")
        _setup_npc_in_game_state(gs, _UUID_B, name="Bandit", occupation="bandit")

        director = _make_director(game_state=gs)
        director.actors = {_UUID_A: AsyncMock(return_value="I attack!"), _UUID_B: AsyncMock(return_value="Me too!")}

        # Both NPCs changed mood from neutral
        gs.npcs[_UUID_A].current_mood = _HOSTILE
        gs.npcs[_UUID_B].current_mood = _HOSTILE

        entries = await _run_with_patched_aggression(
            _AlwaysAttacks(),
            director._check_retaliation({_UUID_A: _NEUTRAL, _UUID_B: _NEUTRAL}),
            combat_replacement=_FixedCombat(),
        )

        assert len(entries) == 1


# ---------------------------------------------------------------------------
# Duplicate NPC name deduplication
# ---------------------------------------------------------------------------


class TestDuplicateNPCNames:
    @pytest.mark.asyncio
    async def test_duplicate_names_one_actor_called(self):
        """When multiple NPCs share the same name, only one Actor is called."""
        gs = _make_game_state()

        # Two NPCs with the same name but different UUIDs
        _setup_npc_in_game_state(gs, _NPC_A, name=_GUARD_NAME, occupation=_NIGHT_GUARD, mood="")
        _setup_npc_in_game_state(gs, _NPC_B, name=_GUARD_NAME, occupation=_DOCK_GUARD, mood="")

        gs.current_scene = Scene(
            location_id="docks",
            description="The docks.",
            npcs_present=[
                SceneNPC(role=_NIGHT_GUARD, uuid=_NPC_A),
                SceneNPC(role=_DOCK_GUARD, uuid=_NPC_B),
            ],
        )

        director = _make_director(
            game_state=gs,
            route_response={
                _ACTION_TYPE: _TALK,
                _TARGETS: [_GUARD],
                _NEEDS_CLARIFICATION: False,
                _DELEGATE_TO: [_ACTOR, _NARRATOR],
            },
        )

        director.actors[_NPC_A] = _make_mock_agent("Hello.")
        director.actors[_NPC_B] = _make_mock_agent("Hi there.")

        await director.act("talk to the guard")

        # Only ONE actor should be called, not both
        total_calls = director.actors[_NPC_A].execute.call_count + director.actors[_NPC_B].execute.call_count
        assert total_calls == 1

    @pytest.mark.asyncio
    async def test_retaliation_skips_duplicate_names(self):
        """When multiple same-name NPCs change mood, only one retaliates."""
        gs = _make_game_state()

        _setup_npc_in_game_state(
            gs,
            _NPC_A,
            name=_GUARD_NAME,
            occupation=_NIGHT_GUARD,
            attributes={_COMBAT_SKILL: 5},
        )
        _setup_npc_in_game_state(
            gs,
            _NPC_B,
            name=_GUARD_NAME,
            occupation=_DOCK_GUARD,
            attributes={_COMBAT_SKILL: 5},
        )

        gs.current_scene = Scene(
            location_id="docks",
            description="The docks.",
            npcs_present=[
                SceneNPC(role=_NIGHT_GUARD, uuid=_NPC_A),
                SceneNPC(role=_DOCK_GUARD, uuid=_NPC_B),
            ],
        )

        director = _make_director(
            game_state=gs,
            route_response={
                _ACTION_TYPE: _INTERACT,
                _IS_AGGRESSIVE: True,
                _TARGETS: [_GUARD],
                _NEEDS_CLARIFICATION: False,
                _DELEGATE_TO: [_ACTOR, _NARRATOR],
            },
        )

        side_effect = _DualMoodMockAct(gs.npcs[_NPC_A], gs.npcs[_NPC_B], [0])
        director.actors[_NPC_A] = _make_mock_agent(None)
        director.actors[_NPC_A].execute = AsyncMock(side_effect=side_effect)
        director.actors[_NPC_B] = _make_mock_agent(None)
        director.actors[_NPC_B].execute = AsyncMock(side_effect=side_effect)

        await _run_with_patched_aggression(
            _AlwaysAttacks(),
            director.act("attack the guard"),
        )

        # 1 dialogue call + 1 retaliation = 2 total (not 2+2=4)
        total_calls = director.actors[_NPC_A].execute.call_count + director.actors[_NPC_B].execute.call_count
        assert total_calls == 2


# ---------------------------------------------------------------------------
# NPC generator call deduplication
# ---------------------------------------------------------------------------


class TestNPCGeneratorDeduplication:
    """NPC generator must be called exactly once per new NPC, not twice.

    Regression guard: previously the explicit 'npc_generator' in delegates
    branch ran in addition to _ensure_targets_in_scene + _init_scene_npcs,
    doubling AI calls for any turn that targeted an uninitialised NPC.
    """

    @pytest.mark.asyncio
    async def test_new_target_npc_generates_exactly_once(self):
        """Targeting an NPC not in the scene triggers one generator call."""
        gs = GameState(setting=_make_setting(), knowledge_graph=KnowledgeGraph())
        gs.current_scene = Scene(
            location_id="market",
            description="The market square.",
            npcs_present=[],  # no NPCs yet
        )

        generated = NPCCard(name="Blacksmith", occupation="blacksmith")
        generated.uuid = "gen-1"

        npc_generator_mock = AsyncMock()
        npc_generator_mock.execute = AsyncMock(return_value=[generated])

        director = _make_director(
            game_state=gs,
            route_response={
                _ACTION_TYPE: _TALK,
                _TARGETS: ["blacksmith"],
                _NEEDS_CLARIFICATION: False,
                _DELEGATE_TO: ["npc_generator", _ACTOR, _NARRATOR],
            },
        )
        director.npc_generator = npc_generator_mock
        # Make the LLM client return a valid string so the actor created by
        # _register_new_npc can complete its _send() call without crashing.
        director.llm_client.send_message = AsyncMock(
            return_value=LLMResponse(content="I'm the blacksmith!", model="test", usage={})
        )

        await director.act("talk to the blacksmith")

        assert npc_generator_mock.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_existing_npc_no_generator_call(self):
        """Targeting an already-initialised NPC must not call the generator."""
        gs = _make_game_state()  # has SceneNPC(role="guard", uuid="npc-1")
        npc = NPCCard(name=_GUARD_NAME, occupation=_CITY_GUARD)
        npc.uuid = _NPC_A
        gs.npcs[_NPC_A] = npc

        npc_generator_mock = AsyncMock()
        npc_generator_mock.execute = AsyncMock(return_value=[])

        director = _make_director(
            game_state=gs,
            route_response={
                _ACTION_TYPE: _TALK,
                _TARGETS: [_GUARD],
                _NEEDS_CLARIFICATION: False,
                # Routing plan says to use npc_generator — used to cause
                # duplication because the explicit branch ran on top of
                # _ensure_targets_in_scene + _init_scene_npcs.
                _DELEGATE_TO: ["npc_generator", _ACTOR, _NARRATOR],
            },
        )
        director.npc_generator = npc_generator_mock
        mock_actor = AsyncMock()
        mock_actor.execute = AsyncMock(return_value="Hello!")
        director.actors[_NPC_A] = mock_actor

        await director.act("talk to the guard")

        assert npc_generator_mock.execute.call_count == 0

    @pytest.mark.asyncio
    async def test_new_npc_announced_to_narrator(self):
        """When a new NPC is generated, narrator receives 'new_npcs' in input."""
        gs = GameState(setting=_make_setting(), knowledge_graph=KnowledgeGraph())
        gs.current_scene = Scene(
            location_id="market",
            description="The market.",
            npcs_present=[],
        )

        generated = NPCCard(name=_MERCHANT_NAME, occupation="cloth merchant")
        generated.uuid = "gen-2"

        director = _make_director(
            game_state=gs,
            route_response={
                _ACTION_TYPE: _TALK,
                _TARGETS: [_MERCHANT],
                _NEEDS_CLARIFICATION: False,
                _DELEGATE_TO: ["npc_generator", _NARRATOR],
            },
        )
        director.npc_generator = _make_mock_agent([generated])
        director.llm_client.send_message = AsyncMock(
            return_value=LLMResponse(content="Fine silks, my friend!", model="test", usage={})
        )

        await director.act("talk to the merchant")

        input_data = _extract_execute_input(director.narrator)
        assert "new_npcs" in input_data
        assert any("Merchant" in desc for desc in input_data["new_npcs"])
