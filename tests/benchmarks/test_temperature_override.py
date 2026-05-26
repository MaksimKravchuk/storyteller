"""Tests for ``load_temperature_overrides`` env-var parsing."""

from __future__ import annotations

import allure
import pytest

from benchmarks.harness._temperature_override import load_temperature_overrides
from tests.benchmarks._temperature_test_env import ALL_ROLES_PINNED, ENV, TEMPS, reset_all_env

pytestmark = [
    allure.epic("Benchmarks"),
    allure.feature("Engine temperature pinning"),
]

_LOAD_STORY = "load_temperature_overrides"


@allure.story(_LOAD_STORY)
@allure.title("Returns None when no override env var is present")
def test_load_returns_none_without_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """No env var → no override (preserve production defaults)."""
    reset_all_env(monkeypatch)
    assert load_temperature_overrides() is None


@allure.story(_LOAD_STORY)
@allure.title("Global var applies to every role")
def test_load_global_applies_to_all_roles(monkeypatch: pytest.MonkeyPatch) -> None:
    """A single BENCHMARK_TEMPERATURE_OVERRIDE pins every role."""
    reset_all_env(monkeypatch)
    monkeypatch.setenv(ENV.global_var, str(TEMPS.pinned))
    assert load_temperature_overrides() == dict(ALL_ROLES_PINNED)


@allure.story(_LOAD_STORY)
@allure.title("Per-role var pins only that role")
def test_load_per_role_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """A per-role var without the global covers only that role."""
    reset_all_env(monkeypatch)
    monkeypatch.setenv(ENV.per_role.format("NARRATOR"), str(TEMPS.partial))
    assert load_temperature_overrides() == {"narrator": TEMPS.partial}


@allure.story(_LOAD_STORY)
@allure.title("Per-role var overrides the global value for that role")
def test_load_per_role_wins_over_global(monkeypatch: pytest.MonkeyPatch) -> None:
    """When both are set, the per-role var wins for its role."""
    reset_all_env(monkeypatch)
    monkeypatch.setenv(ENV.global_var, str(TEMPS.pinned))
    monkeypatch.setenv(ENV.per_role.format("NARRATOR"), str(TEMPS.other))
    assert load_temperature_overrides() == {
        "director": TEMPS.pinned,
        "agent": TEMPS.pinned,
        "narrator": TEMPS.other,
        "dramaturge": TEMPS.pinned,
    }


@allure.story(_LOAD_STORY)
@allure.title("Unparseable values are ignored")
def test_load_ignores_garbage(monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-numeric env var falls through to None for that slot."""
    reset_all_env(monkeypatch)
    monkeypatch.setenv(ENV.global_var, "not-a-float")
    assert load_temperature_overrides() is None
