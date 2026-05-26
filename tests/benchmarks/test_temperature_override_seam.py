"""Consumer-seam tests: env override flows into the engine factory call.

These are the load-bearing assertions for issue #278 — that the env var
loaded by ``load_temperature_overrides`` reaches the engine factory's
``temperature_override`` kwarg through ``_prepare_engine``.
"""

from __future__ import annotations

import allure
import pytest

from tests.benchmarks._temperature_test_env import (
    ALL_ROLES_PINNED,
    ENV,
    TEMPS,
    invoke_prepare_engine_with_factory_mock,
    reset_all_env,
)

pytestmark = [
    allure.epic("Benchmarks"),
    allure.feature("Engine temperature pinning"),
]

_SEAM_STORY = "Consumer seam — benchmark _prepare_engine"


@allure.story(_SEAM_STORY)
@allure.title("Env override flows into create_engine's temperature_override kwarg")
@pytest.mark.asyncio
async def test_prepare_engine_forwards_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Setting the env var must flow all the way to ``create_engine``."""
    reset_all_env(monkeypatch)
    monkeypatch.setenv(ENV.global_var, str(TEMPS.pinned))

    captured_kwargs = await invoke_prepare_engine_with_factory_mock()
    assert captured_kwargs["temperature_override"] == dict(ALL_ROLES_PINNED)


@allure.story(_SEAM_STORY)
@allure.title("Absent env vars pass temperature_override=None to the factory")
@pytest.mark.asyncio
async def test_prepare_engine_no_override_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without the env var, the factory must receive ``None`` — production behaviour."""
    reset_all_env(monkeypatch)

    captured_kwargs = await invoke_prepare_engine_with_factory_mock()
    assert captured_kwargs["temperature_override"] is None
