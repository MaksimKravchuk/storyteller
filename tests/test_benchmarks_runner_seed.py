"""Tests for the harness dice-seed derivation."""

from __future__ import annotations

import allure

from benchmarks.harness.runner import _dice_seed


@allure.epic("Benchmark determinism")
@allure.feature("Per-scenario dice seed")
class TestDiceSeed:
    """``_dice_seed`` is stable per (scenario, iteration) and varies across both."""

    @allure.story("Stability")
    @allure.title("Same scenario + iteration always yields the same seed")
    def test_seed_is_stable(self) -> None:
        assert _dice_seed("npc_autonomy_murder_plot", 0) == _dice_seed("npc_autonomy_murder_plot", 0)

    @allure.story("Variation")
    @allure.title("Iteration index changes the seed so dice vary across iterations")
    def test_seed_varies_by_iteration(self) -> None:
        assert _dice_seed("npc_autonomy_murder_plot", 0) != _dice_seed("npc_autonomy_murder_plot", 1)

    @allure.story("Variation")
    @allure.title("Scenario id changes the seed so scenarios roll independently")
    def test_seed_varies_by_scenario(self) -> None:
        assert _dice_seed("scenario_a", 3) != _dice_seed("scenario_b", 3)
