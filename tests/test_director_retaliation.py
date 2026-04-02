"""Tests for Director NPC retaliation after mood change."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from models.npc_card import NPCCard
from tests.director_helpers import make_director, make_game_state, make_mock_agent, setup_npc

_HOSTILE = "hostile"
_NEUTRAL = "neutral"
_NPC_A = "npc-1"
_GUARD = "guard"
_BANDIT_FIRST = "uuid-1"
_BANDIT_SECOND = "uuid-2"
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
    """Run a coroutine with roll_aggression (and optionally roll_combat) patched."""
    from cast import director_dialogue as dlg_module
    from cast import director_retaliation as ret_module

    original_roll = ret_module.roll_aggression
    original_combat = ret_module.roll_combat if combat_replacement else None
    original_dlg = getattr(dlg_module, "roll_combat", None) if combat_replacement else None
    ret_module.roll_aggression = replacement  # type: ignore[assignment]
    if combat_replacement:
        ret_module.roll_combat = combat_replacement  # type: ignore[assignment]
        dlg_module.roll_combat = combat_replacement  # type: ignore[assignment]
    try:
        return await coro
    except Exception:
        raise
    finally:
        ret_module.roll_aggression = original_roll
        if combat_replacement:
            ret_module.roll_combat = original_combat  # type: ignore[assignment]
            if original_dlg is not None:
                dlg_module.roll_combat = original_dlg  # type: ignore[assignment]


def _make_aggression_stub(will_attack: bool) -> Any:
    """Create a roll_aggression replacement with a fixed will_attack outcome."""
    roll_value = _ATTACK_ROLL if will_attack else 2
    return _DiceCallable(will_attack=will_attack, roll_value=roll_value)


def _fixed_combat(combat_skill_val: int, _rng: Any = None) -> Any:
    """roll_combat replacement with fixed outcome."""
    from cast.dice import CombatOutcome, CombatRoll

    return CombatRoll(
        outcome=CombatOutcome.NPC_OVERPOWERS,
        npc_roll=_ATTACK_ROLL,
        player_roll=5,
        npc_bonus=combat_skill_val,
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
        return "*shoves you back*"

    def _mood_change(self):
        self._call_count[0] += 1
        self._npc.current_mood = _HOSTILE
        if self._call_count[0] == 1:
            return "*blocks the strike*\n[MOOD: {0}]".format(_HOSTILE)
        return "*retaliates fiercely*\n[MOOD: {0}]".format(_HOSTILE)


class TestNPCRetaliation:
    @pytest.mark.asyncio
    async def test_retaliation_on_mood_change_to_hostile(self):
        gs = make_game_state()
        npc, director = self._setup_aggressive_npc(gs)
        director._actors[_NPC_A] = self._mock_actor_with(_SideEffect(npc, tracking=True))

        await _run_patched(_make_aggression_stub(True), director.act("attack the guard"))

        actor_ref = director._actors[_NPC_A]
        assert actor_ref.execute.call_count == 2
        second = actor_ref.execute.call_args_list[1]
        assert "retaliates" in (second.kwargs.get("input_data") or second.args[0])
        assert "[DICE ROLL:" in (second.kwargs.get("input_data") or second.args[0])

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
        mock_actor.act = AsyncMock(return_value="Hello there.")
        mock_actor.execute = AsyncMock(return_value="Hello there.")
        director._actors[_NPC_A] = mock_actor

        await director.act("greet the guard")
        assert mock_actor.execute.call_count == 1

    @pytest.mark.asyncio
    async def test_no_retaliation_when_dice_fail(self):
        gs = make_game_state()
        npc = setup_npc(gs, _NPC_A, name="Guard", occupation=_GUARD)
        director = make_director(game_state=gs, route_response=_aggressive_route())
        effect = _SideEffect(npc)

        actor_a = make_mock_agent(None)
        actor_a.act = AsyncMock(side_effect=effect)
        actor_a.execute = AsyncMock(side_effect=effect)
        director._actors[_NPC_A] = actor_a

        await _run_patched(_make_aggression_stub(False), director.act("punch the guard"))
        assert director._actors[_NPC_A].execute.call_count == 1

    @pytest.mark.asyncio
    async def test_retaliation_deduplication_by_name(self):
        gs = make_game_state()
        setup_npc(gs, _BANDIT_FIRST, name="Bandit", occupation="bandit")
        setup_npc(gs, _BANDIT_SECOND, name="Bandit", occupation="bandit")

        director = make_director(game_state=gs)
        director._actors[_BANDIT_FIRST] = AsyncMock(return_value="I attack!")
        director._actors[_BANDIT_SECOND] = AsyncMock(return_value="Me too!")

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
