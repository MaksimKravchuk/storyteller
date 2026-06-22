"""Tests for the deterministic dice seam (benchmark seed base + per-task RNG)."""

from __future__ import annotations

import contextvars
from collections.abc import Iterator

import allure
import pytest

from cast.dice import ContestType, roll_contest, seed_task_dice, set_dice_seed_base


@pytest.fixture(autouse=True)
def _reset_dice_seed() -> Iterator[None]:
    """Ensure the seed base never leaks between tests."""
    yield
    set_dice_seed_base(None)


def _roll_outcomes(count: int) -> list[tuple[int, int]]:
    rolls = [roll_contest(ContestType.COMBAT, 3, 3) for _ in range(count)]
    return [(roll.actor_roll, roll.target_roll) for roll in rolls]


def _seed_and_roll(key: str) -> tuple[int, int]:
    """Seed this (copied) context for ``key`` and return one contest's d20s."""
    seed_task_dice(key)
    roll = roll_contest(ContestType.COMBAT, 0, 0)
    return roll.actor_roll, roll.target_roll


def _roll_in_fresh_context(key: str) -> tuple[int, int]:
    """Run :func:`_seed_and_roll` in an isolated copied context (mimics a task)."""
    return contextvars.copy_context().run(_seed_and_roll, key)


@allure.epic("Benchmark determinism")
@allure.feature("Deterministic dice seam")
class TestDiceSeedBase:
    """``set_dice_seed_base`` makes dice reproducible; production stays unseeded."""

    @allure.story("Reproducibility")
    @allure.title("Re-installing the same base reproduces the exact roll sequence")
    def test_same_base_reproduces_rolls(self) -> None:
        set_dice_seed_base(20260622)
        first = _roll_outcomes(8)
        set_dice_seed_base(20260622)
        second = _roll_outcomes(8)

        assert first == second

    @allure.story("Reproducibility")
    @allure.title("Different bases yield different roll sequences")
    def test_different_bases_diverge(self) -> None:
        set_dice_seed_base(1)
        first = _roll_outcomes(12)
        set_dice_seed_base(2)
        second = _roll_outcomes(12)

        assert first != second

    @allure.story("Production fallback")
    @allure.title("With no base installed, rolls fall back to a fresh per-call RNG")
    def test_unseeded_fallback_in_range(self) -> None:
        set_dice_seed_base(None)
        roll = roll_contest(ContestType.COMBAT, 3, 3)

        assert 1 <= roll.actor_roll <= 20
        assert 1 <= roll.target_roll <= 20


@allure.epic("Benchmark determinism")
@allure.feature("Deterministic dice seam")
class TestPerTaskSeeding:
    """``seed_task_dice`` keeps concurrent (context-copied) rolls order-independent."""

    @allure.story("Order independence")
    @allure.title("Two isolated contexts seeded by the same key roll identically regardless of order")
    def test_same_key_same_roll_across_contexts(self) -> None:
        set_dice_seed_base(42)

        # Same key in two separate copied contexts → identical rolls, proving the
        # outcome does not depend on which "task" ran first.
        assert _roll_in_fresh_context("npc-A") == _roll_in_fresh_context("npc-A")

    @allure.story("Order independence")
    @allure.title("Different per-task keys produce independent rolls (no degeneracy)")
    def test_distinct_keys_roll_independently(self) -> None:
        set_dice_seed_base(42)
        seed_task_dice("npc-A")
        first = roll_contest(ContestType.COMBAT, 0, 0)
        seed_task_dice("npc-B")
        second = roll_contest(ContestType.COMBAT, 0, 0)

        assert (first.actor_roll, first.target_roll) != (second.actor_roll, second.target_roll)

    @allure.story("Production fallback")
    @allure.title("seed_task_dice is a no-op when no base is installed")
    def test_seed_task_dice_noop_unseeded(self) -> None:
        set_dice_seed_base(None)
        seed_task_dice("npc-A")  # must not raise or seed anything
        roll = roll_contest(ContestType.COMBAT, 0, 0)

        assert 1 <= roll.actor_roll <= 20
