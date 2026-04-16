"""Validation tests for frozen benchmark types — invariant enforcement."""

from __future__ import annotations

import allure
import pytest

from benchmarks.harness.types._elements import (
    KIND_DETERMINISTIC,
    KIND_EVIDENCE_LLM,
    DeterministicResult,
    Element,
    EvidencePromptSpec,
)
from benchmarks.harness.types._scenarios import Scenario, ScriptTurn


def _good_script() -> tuple[ScriptTurn, ...]:
    return (ScriptTurn(player_action="look"),)


def _good_elements() -> tuple[Element, ...]:
    return (
        Element(
            id="e1",
            label="e1",
            base_value=1,
            kind=KIND_DETERMINISTIC,
            check=lambda _c, _s: DeterministicResult(awarded=0, reason=""),
        ),
    )


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestDeterministicResult:
    @allure.story("Type invariants")
    @allure.title("DeterministicResult rejects negative awarded values at construction")
    def test_negative_awarded_raises(self):
        with pytest.raises(ValueError, match="non-negative"):
            DeterministicResult(awarded=-1, reason="bad")

    @allure.story("Type invariants")
    @allure.title("DeterministicResult accepts zero and positive awarded values")
    def test_zero_and_positive_allowed(self):
        DeterministicResult(awarded=0, reason="none")
        DeterministicResult(awarded=3, reason="full")


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestElementValidation:
    @allure.story("Type invariants")
    @allure.title("Element rejects a non-positive base_value at construction")
    def test_zero_base_value_raises(self):
        with pytest.raises(ValueError, match="base_value must be positive"):
            Element(
                id="e",
                label="e",
                base_value=0,
                kind=KIND_DETERMINISTIC,
                check=lambda _c, _s: DeterministicResult(awarded=0, reason=""),
            )

    @allure.story("Type invariants")
    @allure.title("Element rejects a deterministic kind paired with an EvidencePromptSpec check")
    def test_deterministic_kind_with_spec_check_raises(self):
        with pytest.raises(TypeError, match="callable check"):
            Element(
                id="e",
                label="e",
                base_value=1,
                kind=KIND_DETERMINISTIC,
                check=EvidencePromptSpec(scenario_brief="", question=""),
            )

    @allure.story("Type invariants")
    @allure.title("Element rejects an evidence_llm kind paired with a callable check")
    def test_evidence_kind_with_callable_check_raises(self):
        with pytest.raises(TypeError, match="EvidencePromptSpec"):
            Element(
                id="e",
                label="e",
                base_value=1,
                kind=KIND_EVIDENCE_LLM,
                check=lambda _c, _s: DeterministicResult(awarded=0, reason=""),
            )


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestScenarioValidation:
    @allure.story("Type invariants")
    @allure.title("Scenario rejects an empty script at construction")
    def test_empty_script_raises(self):
        with pytest.raises(ValueError, match="at least one script turn"):
            Scenario(
                id="s",
                label="s",
                build_state=lambda: None,  # type: ignore[arg-type,return-value]
                script=(),
                elements=_good_elements(),
            )

    @allure.story("Type invariants")
    @allure.title("Scenario rejects an empty elements tuple at construction")
    def test_empty_elements_raises(self):
        with pytest.raises(ValueError, match="at least one element"):
            Scenario(
                id="s",
                label="s",
                build_state=lambda: None,  # type: ignore[arg-type,return-value]
                script=_good_script(),
                elements=(),
            )

    @allure.story("Type invariants")
    @allure.title("Scenario rejects duplicate element ids that would corrupt report aggregation")
    def test_duplicate_element_ids_raise(self):
        duplicate = Element(
            id="dup",
            label="dup",
            base_value=1,
            kind=KIND_DETERMINISTIC,
            check=lambda _c, _s: DeterministicResult(awarded=0, reason=""),
        )
        with pytest.raises(ValueError, match="duplicate element ids"):
            Scenario(
                id="s",
                label="s",
                build_state=lambda: None,  # type: ignore[arg-type,return-value]
                script=_good_script(),
                elements=(duplicate, duplicate),
            )
