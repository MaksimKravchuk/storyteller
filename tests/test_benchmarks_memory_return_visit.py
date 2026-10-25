"""Deterministic rubric checks of the ``memory_return_visit`` benchmark scenario."""

from __future__ import annotations

import allure

from benchmarks.scenarios.memory_return_visit import elements as rubric
from benchmarks.scenarios.memory_return_visit.state import EIRA_UUID, build_state
from models.game_state import GameState
from models.npc_card import NPCCard
from models.scene import Scene
from tests._uuid_helpers import make_uuid

_ELSEWHERE = make_uuid("return-visit-elsewhere")


def _seed() -> GameState:
    return build_state().game_state


@allure.epic("Benchmarks")
@allure.feature("Scenario rubric")
@allure.story("memory_return_visit")
class TestReturnVisitRubric:
    @allure.title("The seeded state passes every deterministic place/identity check")
    def test_seed_state_passes(self) -> None:
        state = _seed()

        assert rubric._eira_back_in_scene([], [state]).awarded == 2
        assert rubric._player_back_at_landing([], [state]).awarded == 1
        assert rubric._single_eira([], [state]).awarded == 1

    @allure.title("A final scene without the original Eira scores zero")
    def test_eira_missing_from_scene(self) -> None:
        state = _seed()
        state.current_scene = Scene(location_id=_ELSEWHERE)

        assert rubric._eira_back_in_scene([], [state]).awarded == 0

    @allure.title("No current scene at all scores zero for Eira's presence")
    def test_no_scene(self) -> None:
        state = _seed()
        state.current_scene = None

        assert rubric._eira_back_in_scene([], [state]).awarded == 0

    @allure.title("Ending at a different location scores zero for the return")
    def test_player_elsewhere(self) -> None:
        state = _seed()
        state.player.location_id = _ELSEWHERE

        assert rubric._player_back_at_landing([], [state]).awarded == 0

    @allure.title("A generated namesake makes the single-Eira check fail")
    def test_duplicate_eira(self) -> None:
        state = _seed()
        namesake = NPCCard(name="eira ", occupation="net-mender")
        state.npcs[namesake.uuid] = namesake

        result = rubric._single_eira([], [state])

        assert result.awarded == 0
        assert EIRA_UUID in state.npcs
        assert "2 NPCs" in result.reason
