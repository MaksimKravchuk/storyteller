"""Tests for Director combat dice integration."""

from __future__ import annotations

import allure
import pytest

from models.npc_card import NPCCard
from tests.director_helpers import make_director, make_game_state, make_mock_actor

_HOSTILE = "hostile"
_NPC_A = "npc-1"
_GUARD_NAME = "Guard"
_CITY_GUARD = "city guard"
_COMBAT_SKILL = "combat_skill"
_INPUT_DATA = "input_data"


@allure.epic("Combat & Action Resolution")
@allure.feature("Combat routing")
class TestCombatDiceIntegration:
    @allure.story("Dice injection into actor input")
    @allure.title("An aggressive player action against a guard injects [DICE ROLL:] and OUTCOME: into actor input")
    @pytest.mark.asyncio
    async def test_aggressive_action_injects_dice_roll(self):
        director, mock_actor = self._build(is_aggressive=True)
        await director.act("punch the guard")
        # First call is dialogue, second is NPC turn
        call_args = mock_actor.execute.call_args_list[0]
        input_text = call_args.kwargs.get(_INPUT_DATA) or call_args.args[0]
        assert "[DICE ROLL:" in input_text
        assert "OUTCOME:" in input_text

    @allure.story("Dice injection into actor input")
    @allure.title("A non-aggressive talk action does not inject any combat dice marker into the actor input")
    @pytest.mark.asyncio
    async def test_non_aggressive_action_no_dice_roll(self):
        director, mock_actor = self._build(is_aggressive=False)
        await director.act("talk to the guard")
        call_args = mock_actor.execute.call_args
        input_text = call_args.kwargs.get(_INPUT_DATA) or call_args.args[0]
        assert "[DICE ROLL:" not in input_text

    @allure.story("Contest roll propagation to narrator")
    @allure.title("The narrator receives the contest_roll attached to each dialogue entry for aggressive actions")
    @pytest.mark.asyncio
    async def test_combat_roll_included_in_dialogue_result(self):
        director, _ = self._build(is_aggressive=True)
        await director.act("attack guard")
        narrator_call = director._executor._narrator.execute.call_args
        raw_input = narrator_call.kwargs.get(_INPUT_DATA) or narrator_call.args[0]
        dialogue = raw_input.dialogue
        assert len(dialogue) == 1
        assert dialogue[0].contest_roll is not None

    @allure.story("Skill bonus defaults")
    @allure.title("An NPC without a combat_skill attribute still receives a default +3 bonus in the combat roll")
    @pytest.mark.asyncio
    async def test_npc_without_combat_skill_uses_default(self):
        director, _ = self._build(is_aggressive=True, combat_skill=0)
        npc = NPCCard(name="Merchant", occupation="merchant")
        npc.uuid = _NPC_A
        director._game_state.npcs[_NPC_A] = npc
        mock_actor = make_mock_actor("*cowers*")
        director._actors[_NPC_A] = mock_actor
        await director.act("punch the merchant")
        # First call is dialogue
        call_args = mock_actor.execute.call_args_list[0]
        input_text = call_args.kwargs.get(_INPUT_DATA) or call_args.args[0]
        assert "+3]" in input_text

    def _build(self, is_aggressive, combat_skill=5):
        gs = make_game_state()
        npc = NPCCard(
            name=_GUARD_NAME,
            occupation=_CITY_GUARD,
            attributes={_COMBAT_SKILL: combat_skill},
        )
        npc.uuid = _NPC_A
        gs.npcs[_NPC_A] = npc
        director = make_director(
            game_state=gs,
            route_response={
                "action_type": "INTERACT",
                "is_aggressive": is_aggressive,
                "targets": ("guard",),
                "needs_clarification": False,
                "delegate_to": ["actor", "narrator"],
            },
        )
        mock_actor = make_mock_actor("*fights back*")
        director._actors[_NPC_A] = mock_actor
        return director, mock_actor
