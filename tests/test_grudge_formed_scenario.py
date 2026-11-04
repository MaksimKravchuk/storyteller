"""No-LLM check that the grudge-formed benchmark rubric scores the off-scene write-back."""

from __future__ import annotations

import copy
from unittest.mock import MagicMock, patch

import allure
import pytest

from benchmarks.harness.scoring import score_deterministic_element
from benchmarks.scenarios.npc_autonomy_grudge_formed.elements import ELEMENTS
from benchmarks.scenarios.npc_autonomy_grudge_formed.state import build_state
from cast.dice import ContestOutcome, ContestRoll, ContestType
from cast.npc_background_tick import NPCBackgroundTicker
from knowledge.memory import MemoryManager

_WOUNDING_ROLL = ContestRoll(
    contest_type=ContestType.COMBAT,
    outcome=ContestOutcome.ACTOR_SUCCEEDS,
    actor_roll=12,
    target_roll=10,
    actor_bonus=0,
    target_bonus=0,
)


@allure.epic("Benchmarks")
@allure.feature("Grudge-formed scenario")
class TestGrudgeFormedScenario:
    """One off-scene wounding round satisfies every deterministic element."""

    @pytest.mark.asyncio
    @allure.story("Off-scene grudge")
    @allure.title("A wounding off-scene contest awards full marks on the grudge rubric")
    async def test_offscene_wound_scores_full_rubric(self) -> None:
        game_state = build_state().game_state
        baseline = copy.deepcopy(game_state)
        ticker = NPCBackgroundTicker(game_state, MemoryManager(game_state.knowledge_graph, MagicMock()))
        with patch("cast.npc_background_tick.roll_contest", return_value=_WOUNDING_ROLL):
            await ticker.tick(hours_advanced=8.0)

        scores = [score_deterministic_element(element, [], [baseline, game_state]) for element in ELEMENTS]

        assert {score.element_id: score.awarded for score in scores} == {
            element.id: element.base_value for element in ELEMENTS
        }

    @allure.story("Off-scene grudge")
    @allure.title("The untouched seed state scores zero on the grudge rubric")
    def test_seed_state_scores_zero(self) -> None:
        game_state = build_state().game_state
        snapshots = [game_state, game_state]
        assert all(score_deterministic_element(element, [], snapshots).awarded == 0 for element in ELEMENTS)
