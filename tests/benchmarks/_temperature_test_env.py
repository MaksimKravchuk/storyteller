"""Shared helpers for benchmark temperature-override tests."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@dataclass(frozen=True)
class _Env:
    """Env-var names involved in the override contract."""

    global_var: str = "BENCHMARK_TEMPERATURE_OVERRIDE"
    per_role: str = "BENCHMARK_{0}_TEMPERATURE"
    roles: tuple[str, ...] = ("DIRECTOR", "AGENT", "NARRATOR", "DRAMATURGE")


@dataclass(frozen=True)
class _Temps:
    """Temperature values used across the test suite."""

    pinned: float = float(0)  # benchmark-pinned T=0 for run-to-run determinism
    partial: float = 0.25
    other: float = 0.4


ENV = _Env()
TEMPS = _Temps()
ALL_ROLES_PINNED: Mapping[str, float] = MappingProxyType(
    {
        "director": TEMPS.pinned,
        "agent": TEMPS.pinned,
        "narrator": TEMPS.pinned,
        "dramaturge": TEMPS.pinned,
    },
)


def reset_all_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Drop the global override var and every per-role override."""
    monkeypatch.delenv(ENV.global_var, raising=False)
    for role in ENV.roles:
        monkeypatch.delenv(ENV.per_role.format(role), raising=False)


async def invoke_prepare_engine_with_factory_mock() -> Mapping[str, object]:
    """Drive ``_prepare_engine`` through a mocked factory and return the kwargs it saw."""
    from benchmarks.harness import _run_execution

    fake_engine = MagicMock(name="engine")
    fake_engine.restore_session = AsyncMock()
    scenario_state = MagicMock(name="scenario_state")
    scenario_state.game_state = MagicMock(name="game_state")
    scenario_state.events = []

    factory_mock = MagicMock(return_value=fake_engine)
    with (
        patch("benchmarks.harness._run_execution.create_engine", factory_mock),
        patch(
            "benchmarks.harness._run_execution.NarratorCapture",
            autospec=True,
        ),
    ):
        await _run_execution._prepare_engine(MagicMock(name="cfg"), scenario_state)
        _, captured_kwargs = factory_mock.call_args
    return captured_kwargs
