"""Tests for the config-driven :func:`build_moderator` factory.

The factory bridges the env-derived ``Config`` to the moderator's
provider list and threshold policy. It must always install the
heuristic provider, opt into OpenAI only when an API key is present,
and return ``None`` when safety is disabled outright.
"""

from __future__ import annotations

from dataclasses import dataclass

import allure

from safety.factory import build_moderator
from safety.heuristic import HeuristicProvider
from safety.openai_provider import OpenAIModerationProvider
from safety.result import ModerationCategory, ModerationSeverity

pytestmark = [
    allure.epic("Engine & LLM Infrastructure"),
    allure.feature("Content safety"),
]


@dataclass
class _CfgStub:
    """Minimal Config-shaped stub covering only the safety fields."""

    safety_enabled: bool = True
    openai_api_key: str | None = None
    safety_threshold_violence: str = "HIGH"
    safety_threshold_sexual: str = "HIGH"
    safety_threshold_sexual_minors: str = "LOW"
    safety_threshold_harassment: str = "HIGH"
    safety_threshold_hate: str = "MEDIUM"
    safety_threshold_self_harm: str = "MEDIUM"
    safety_threshold_illicit: str = "HIGH"
    safety_threshold_prompt_injection: str = "MEDIUM"


@allure.story("Factory wiring")
@allure.title("build_moderator returns None when safety_enabled is False")
def test_build_moderator_disabled_returns_none() -> None:
    cfg = _CfgStub(safety_enabled=False)
    assert build_moderator(cfg) is None  # type: ignore[arg-type]


@allure.story("Factory wiring")
@allure.title("build_moderator always installs the HeuristicProvider even with no OpenAI key")
def test_build_moderator_always_installs_heuristic() -> None:
    cfg = _CfgStub(safety_enabled=True, openai_api_key=None)
    moderator = build_moderator(cfg)  # type: ignore[arg-type]
    assert moderator is not None
    assert any(isinstance(provider, HeuristicProvider) for provider in moderator.providers)
    assert not any(isinstance(provider, OpenAIModerationProvider) for provider in moderator.providers)


@allure.story("Factory wiring")
@allure.title("build_moderator adds an OpenAIModerationProvider when an API key is configured")
def test_build_moderator_adds_openai_when_key_present() -> None:
    cfg = _CfgStub(safety_enabled=True, openai_api_key="sk-fake-key")
    moderator = build_moderator(cfg)  # type: ignore[arg-type]
    assert moderator is not None
    assert any(isinstance(provider, OpenAIModerationProvider) for provider in moderator.providers)


@allure.story("Factory wiring")
@allure.title("build_moderator translates the threshold env strings into ModerationSeverity values")
def test_build_moderator_parses_threshold_strings() -> None:
    cfg = _CfgStub(
        safety_enabled=True,
        safety_threshold_violence="medium",  # lower-case + non-default
    )
    moderator = build_moderator(cfg)  # type: ignore[arg-type]
    assert moderator is not None
    assert moderator.thresholds.threshold_for(ModerationCategory.VIOLENCE) == ModerationSeverity.MEDIUM


@allure.story("Factory wiring")
@allure.title("build_moderator falls back to the default threshold for an unknown severity name")
def test_build_moderator_falls_back_on_unknown_severity() -> None:
    cfg = _CfgStub(safety_enabled=True, safety_threshold_violence="not-a-severity")
    moderator = build_moderator(cfg)  # type: ignore[arg-type]
    assert moderator is not None
    # The default for violence is HIGH, so a typo must not silently widen the gate.
    assert moderator.thresholds.threshold_for(ModerationCategory.VIOLENCE) == ModerationSeverity.HIGH
