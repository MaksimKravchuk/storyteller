"""Tests for Director NPC retaliation after mood change."""

from __future__ import annotations

from contextlib import ExitStack
from typing import Any
from unittest.mock import AsyncMock, patch

import allure
import pytest

from cast.dice import ContestOutcome, ContestRoll, ContestType
from cast.director_retaliation import RetaliationHandler
from models.npc_card import NPCCard
from tests.director_helpers import (
    actor_reply,
    make_director,
    make_game_state,
    make_mock_actor,
    make_uuid,
    setup_npc,
)

_HOSTILE = "hostile"
_NEUTRAL = "neutral"
_NPC_A = make_uuid("npc-1")
_GUARD = "guard"
_BANDIT_FIRST = make_uuid("uuid-1")
_BANDIT_SECOND = make_uuid("uuid-2")
_ATTACK_ROLL = 15


def _aggressive_route():
    """Build an aggressive interaction route response."""
    return {
        "action_type": "INTERACT",
        "is_aggressive": True,
        "targets": (_GUARD,),
        "needs_clarification": False,
        "delegate_to": ["actor", "narrator"],
    }


async def _run_patched(replacement, coro, combat_replacement=None):
    """Run a coroutine with roll_aggression (and optionally roll_contest) patched."""
    from cast import director_retaliation as ret_module

    with ExitStack() as stack:
        stack.enter_context(patch.object(ret_module, "roll_aggression", replacement))
        if combat_replacement:
            stack.enter_context(patch.object(ret_module, "roll_contest", combat_replacement))
        return await coro


def _make_aggression_stub(will_attack: bool) -> Any:
    """Create a roll_aggression replacement with a fixed will_attack outcome."""
    roll_value = _ATTACK_ROLL if will_attack else 2
    return _DiceCallable(will_attack=will_attack, roll_value=roll_value)


def _call_input(call: Any) -> str:
    """Extract the ``input_data`` argument from an AsyncMock call record."""
    return call.kwargs.get("input_data") or call.args[0]


def _fixed_combat(contest_type: ContestType, actor_skill: int, target_skill: int, _rng: Any = None) -> ContestRoll:
    """roll_contest replacement with fixed TARGET_DOMINATES outcome."""
    return ContestRoll(
        contest_type=contest_type,
        outcome=ContestOutcome.TARGET_DOMINATES,
        actor_roll=5,
        target_roll=_ATTACK_ROLL,
        actor_bonus=actor_skill,
        target_bonus=target_skill,
    )


class _DiceCallable:
    """Callable that produces AggressionRoll results."""

    def __init__(self, will_attack: bool, roll_value: int):
        self._will_attack = will_attack
        self._roll_value = roll_value

    def __call__(self, mood: str, _rng: Any = None) -> Any:
        from cast.dice import AggressionRoll

        return AggressionRoll(
            will_attack=self._will_attack,
            roll=self._roll_value,
            threshold=5,
            mood=mood,
        )


class _SideEffect:
    """Callable side effects for NPC mock actors in retaliation tests."""

    def __init__(self, npc, *, tracking=False):
        self._npc = npc
        self._call_count = [0] if tracking else None

    def __call__(self, input_data, context):
        if self._call_count is not None:
            return self._mood_change()
        self._npc.current_mood = _HOSTILE
        return actor_reply(text="*shoves you back*")

    def _mood_change(self):
        self._call_count[0] += 1
        self._npc.current_mood = _HOSTILE
        if self._call_count[0] == 1:
            return actor_reply(text="*blocks the strike*")
        return actor_reply(text="*retaliates fiercely*")


@allure.epic("Combat & Action Resolution")
@allure.feature("NPC retaliation")
class TestNPCRetaliation:
    @allure.story("Retaliation on mood change")
    @allure.title("An NPC directly attacked by the player resolves combat in a single actor call, not two")
    @pytest.mark.asyncio
    async def test_aggressive_target_not_retaliated_twice(self):
        """Regression: when the player attacks an NPC, the dialogue call already
        rolls combat dice and lets the Actor physically retaliate in its response.
        A second ``actor.execute`` call from the retaliation phase is redundant
        and corrupts narration. See plan: vectorized-squishing-curry.md.
        """
        gs = make_game_state()
        npc, director = self._setup_aggressive_npc(gs)
        director._actors[_NPC_A] = self._mock_actor_with(_SideEffect(npc, tracking=True))

        await _run_patched(_make_aggression_stub(True), director.act("attack the guard"))

        actor_ref = director._actors[_NPC_A]
        # 2 calls: dialogue (combat dice resolves the aggression) + NPC turn.
        # No separate retaliation call — the dialogue response already handled it.
        assert actor_ref.execute.call_count == 2
        call_list = actor_ref.execute.call_args_list
        first_input = _call_input(call_list[0])
        assert "[DICE ROLL: actor" in first_input
        for call in call_list:
            assert "retaliates against the player" not in _call_input(call)

    @allure.story("Retaliation on mood change")
    @allure.title(
        "A bystander NPC whose mood flips in a neighbour's retaliation check still gets its own retaliation call"
    )
    @pytest.mark.asyncio
    async def test_bystander_not_targeted_still_retaliates(self):
        """Retaliation is still fired for NPCs that were NOT in the player's
        target list but whose mood flipped through some other channel. The
        fix must only suppress combat-engaged direct targets.
        """
        gs = make_game_state()
        bystander = setup_npc(gs, _NPC_A, name="Bystander", occupation="onlooker")
        bystander.current_mood = _HOSTILE
        bystander_actor = make_mock_actor("*lunges at the player*")
        handler = RetaliationHandler(gs, {_NPC_A: bystander_actor})

        entries = await _run_patched(
            _make_aggression_stub(True),
            handler.check_retaliation({_NPC_A: _NEUTRAL}, skip_uuids={make_uuid("other-uuid")}),
            combat_replacement=_fixed_combat,
        )

        assert len(entries) == 1
        assert bystander_actor.execute.call_count == 1

    @allure.story("Retaliation on mood change")
    @allure.title("An NPC whose dialogue combat was already rolled is filtered out of the retaliation phase")
    @pytest.mark.asyncio
    async def test_check_retaliation_honours_skip_uuids(self):
        """Direct unit test for the skip_uuids parameter. Feeds a hostile NPC
        into the retaliation handler and verifies that listing it in
        ``skip_uuids`` suppresses the call entirely.
        """
        gs = make_game_state()
        target = setup_npc(gs, _NPC_A, name="Guard", occupation=_GUARD)
        target.current_mood = _HOSTILE
        actor = make_mock_actor("*should not be called*")
        handler = RetaliationHandler(gs, {_NPC_A: actor})

        entries = await _run_patched(
            _make_aggression_stub(True),
            handler.check_retaliation({_NPC_A: _NEUTRAL}, skip_uuids={_NPC_A}),
            combat_replacement=_fixed_combat,
        )

        assert entries == []
        assert actor.execute.call_count == 0

    @allure.story("Retaliation on mood change")
    @allure.title("An NPC that stays neutral through a friendly greet receives no retaliation call")
    @pytest.mark.asyncio
    async def test_no_retaliation_when_mood_unchanged(self):
        gs = make_game_state()
        npc = NPCCard(name="Guard", occupation=_GUARD)
        npc.uuid = _NPC_A
        npc.current_mood = _NEUTRAL
        gs.npcs[_NPC_A] = npc

        director = make_director(
            game_state=gs,
            route_response={
                "action_type": "TALK",
                "targets": (_GUARD,),
                "needs_clarification": False,
                "delegate_to": ["actor", "narrator"],
            },
        )
        mock_actor = AsyncMock()
        hello_reply = actor_reply(text="Hello there.")
        idle_reply = actor_reply(text='{"action": "nods", "type": "IDLE", "target": null}')
        mock_actor.act = AsyncMock(return_value=hello_reply)
        # 1st call: dialogue, 2nd call: NPC turn
        mock_actor.execute = AsyncMock(side_effect=[hello_reply, idle_reply])
        director._actors[_NPC_A] = mock_actor

        await director.act("greet the guard")
        # 2 calls: dialogue + NPC turn (no retaliation since mood unchanged)
        assert mock_actor.execute.call_count == 2

    @allure.story("Aggression roll integration")
    @allure.title("A newly hostile NPC whose aggression roll fails does not retaliate this turn")
    @pytest.mark.asyncio
    async def test_no_retaliation_when_dice_fail(self):
        gs = make_game_state()
        npc = setup_npc(gs, _NPC_A, name="Guard", occupation=_GUARD)
        director = make_director(game_state=gs, route_response=_aggressive_route())
        effect = _SideEffect(npc)

        actor_a = make_mock_actor("")
        actor_a.act = AsyncMock(side_effect=effect)
        actor_a.execute = AsyncMock(side_effect=effect)
        director._actors[_NPC_A] = actor_a

        await _run_patched(_make_aggression_stub(False), director.act("punch the guard"))
        # 2 calls: dialogue + NPC turn (no retaliation since dice failed)
        assert director._actors[_NPC_A].execute.call_count == 2

    @allure.story("Retaliation on mood change")
    @allure.title("Two NPCs sharing the same display name collapse into a single retaliation entry")
    @pytest.mark.asyncio
    async def test_retaliation_deduplication_by_name(self):
        gs = make_game_state()
        setup_npc(gs, _BANDIT_FIRST, name="Bandit", occupation="bandit")
        setup_npc(gs, _BANDIT_SECOND, name="Bandit", occupation="bandit")

        director = make_director(game_state=gs)
        director._actors[_BANDIT_FIRST] = make_mock_actor("I attack!")
        director._actors[_BANDIT_SECOND] = make_mock_actor("Me too!")

        gs.npcs[_BANDIT_FIRST].current_mood = _HOSTILE
        gs.npcs[_BANDIT_SECOND].current_mood = _HOSTILE

        entries = await _run_patched(
            _make_aggression_stub(True),
            director._retaliation.check_retaliation({_BANDIT_FIRST: _NEUTRAL, _BANDIT_SECOND: _NEUTRAL}),
            combat_replacement=_fixed_combat,
        )
        assert len(entries) == 1

    def _setup_aggressive_npc(self, gs):
        """Create NPC and director for aggressive interaction tests."""
        npc = NPCCard(name="Guard", occupation="city guard", attributes={"combat_skill": 7})
        npc.uuid = _NPC_A
        npc.current_mood = _NEUTRAL
        gs.npcs[_NPC_A] = npc
        director = make_director(game_state=gs, route_response=_aggressive_route())
        return npc, director

    def _mock_actor_with(self, effect):
        """Create a mock actor using the given side effect."""
        mock_actor = AsyncMock()
        mock_actor.act = AsyncMock(side_effect=effect)
        mock_actor.execute = AsyncMock(side_effect=effect)
        return mock_actor
