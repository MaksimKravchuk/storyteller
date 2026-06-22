"""Tests for the installable default dice RNG (benchmark determinism seam)."""

from __future__ import annotations

import random
from collections.abc import Iterator

import allure
import pytest

from cast.dice import ContestType, roll_contest, set_default_rng


@pytest.fixture(autouse=True)
def _reset_default_rng() -> Iterator[None]:
    """Ensure the injected RNG never leaks between tests."""
    yield
    set_default_rng(None)


def _roll_outcomes(count: int) -> list[tuple[int, int]]:
    rolls = [roll_contest(ContestType.COMBAT, 3, 3) for _ in range(count)]
    return [(roll.actor_roll, roll.target_roll) for roll in rolls]


@allure.epic("Benchmark determinism")
@allure.feature("Installable dice RNG")
class TestDefaultDiceRng:
    """``set_default_rng`` installs a seeded RNG so dice rolls reproduce."""

    @allure.story("Reproducibility")
    @allure.title("Re-installing the same seed reproduces the exact roll sequence")
    def test_same_seed_reproduces_rolls(self) -> None:
        set_default_rng(random.Random(20260622))
        first = _roll_outcomes(8)
        set_default_rng(random.Random(20260622))
        second = _roll_outcomes(8)

        assert first == second

    @allure.story("Reproducibility")
    @allure.title("The installed RNG is actually consumed for both d20 draws")
    def test_installed_rng_drives_the_rolls(self) -> None:
        set_default_rng(random.Random(7))
        roll = roll_contest(ContestType.COMBAT, 0, 0)

        oracle = random.Random(7)
        assert roll.actor_roll == oracle.randint(1, 20)
        assert roll.target_roll == oracle.randint(1, 20)

    @allure.story("Reproducibility")
    @allure.title("Different seeds yield different roll sequences")
    def test_different_seeds_diverge(self) -> None:
        set_default_rng(random.Random(1))
        first = _roll_outcomes(12)
        set_default_rng(random.Random(2))
        second = _roll_outcomes(12)

        assert first != second

    @allure.story("Production fallback")
    @allure.title("Clearing the RNG restores the per-call fresh-RNG fallback")
    def test_clearing_restores_fallback(self) -> None:
        set_default_rng(None)
        roll = roll_contest(ContestType.COMBAT, 3, 3)

        assert 1 <= roll.actor_roll <= 20
        assert 1 <= roll.target_roll <= 20
