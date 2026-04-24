"""Unit tests for the reusable prose-quality element factories and their wiring.

Covers:
- :mod:`benchmarks.harness.prose_quality` factory functions return well-formed
  :class:`EvidencePromptSpec` instances (non-empty brief + question, correct
  ``evidence_turn`` forwarding).
- The four new prose-quality elements in the escalation scenario have the
  correct kind and spec shape.

No LLM calls are made — evidence-LLM elements are verified structurally only.
"""

from __future__ import annotations

import allure
import pytest

from benchmarks.harness.prose_quality import (
    no_action_repetition,
    no_cliches,
    no_invented_inner_states,
    no_purple_prose,
)
from benchmarks.harness.types._elements import (
    KIND_EVIDENCE_LLM,
    EvidencePromptSpec,
)
from benchmarks.scenarios.escalation_guard_assault.elements import ELEMENTS

_BRIEF = "A lone Roman sentry is assaulted repeatedly. Prose quality is under test."
_PROSE_ELEMENT_IDS = frozenset(
    (
        "narration_no_cliches",
        "narration_no_purple_prose",
        "narration_no_repetition",
        "narration_no_invented_inner_states",
    )
)


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestProseQualityFactories:
    @allure.story("Prose quality elements")
    @allure.title("no_cliches returns an EvidencePromptSpec with a non-empty brief and question")
    def test_no_cliches_returns_spec(self):
        spec = no_cliches(_BRIEF)

        assert isinstance(spec, EvidencePromptSpec)
        assert spec.scenario_brief
        assert spec.question

    @allure.story("Prose quality elements")
    @allure.title("no_purple_prose returns an EvidencePromptSpec with a non-empty brief and question")
    def test_no_purple_prose_returns_spec(self):
        spec = no_purple_prose(_BRIEF)

        assert isinstance(spec, EvidencePromptSpec)
        assert spec.scenario_brief
        assert spec.question

    @allure.story("Prose quality elements")
    @allure.title("no_action_repetition returns an EvidencePromptSpec with a non-empty brief and question")
    def test_no_action_repetition_returns_spec(self):
        spec = no_action_repetition(_BRIEF)

        assert isinstance(spec, EvidencePromptSpec)
        assert spec.scenario_brief
        assert spec.question

    @allure.story("Prose quality elements")
    @allure.title("no_invented_inner_states returns an EvidencePromptSpec with a non-empty brief and question")
    def test_no_invented_inner_states_returns_spec(self):
        spec = no_invented_inner_states(_BRIEF)

        assert isinstance(spec, EvidencePromptSpec)
        assert spec.scenario_brief
        assert spec.question

    @allure.story("Prose quality elements")
    @allure.title("All factories forward the scenario_brief argument unchanged")
    @pytest.mark.parametrize(
        "factory",
        [no_cliches, no_purple_prose, no_action_repetition, no_invented_inner_states],
    )
    def test_brief_is_forwarded(self, factory):
        spec = factory(_BRIEF)

        assert spec.scenario_brief == _BRIEF

    @allure.story("Prose quality elements")
    @allure.title("All factories default evidence_turn to None when no turn index is provided")
    @pytest.mark.parametrize(
        "factory",
        [no_cliches, no_purple_prose, no_action_repetition, no_invented_inner_states],
    )
    def test_evidence_turn_defaults_to_none(self, factory):
        spec = factory(_BRIEF)

        assert spec.evidence_turn is None

    @allure.story("Prose quality elements")
    @allure.title("All factories forward an explicit evidence_turn integer to the spec")
    @pytest.mark.parametrize(
        "factory",
        [no_cliches, no_purple_prose, no_action_repetition, no_invented_inner_states],
    )
    def test_evidence_turn_is_forwarded(self, factory):
        spec = factory(_BRIEF, evidence_turn=2)

        assert spec.evidence_turn == 2

    @allure.story("Prose quality elements")
    @allure.title("Each factory produces a distinct question so the four checks remain independent")
    def test_all_questions_are_distinct(self):
        specs = [
            no_cliches(_BRIEF),
            no_purple_prose(_BRIEF),
            no_action_repetition(_BRIEF),
            no_invented_inner_states(_BRIEF),
        ]
        questions = [spec.question for spec in specs]

        assert len(set(questions)) == len(questions)


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestEscalationProseElements:
    @allure.story("Escalation scenario rubric")
    @allure.title("Escalation scenario exposes all four prose-quality element ids")
    def test_prose_element_ids_present(self):
        element_ids = {element.id for element in ELEMENTS}

        assert _PROSE_ELEMENT_IDS.issubset(element_ids)

    @allure.story("Escalation scenario rubric")
    @allure.title("All four prose-quality elements carry KIND_EVIDENCE_LLM kind")
    def test_prose_elements_are_evidence_llm(self):
        prose_elements = [element for element in ELEMENTS if element.id in _PROSE_ELEMENT_IDS]

        assert len(prose_elements) == len(_PROSE_ELEMENT_IDS)
        for element in prose_elements:
            assert element.kind == KIND_EVIDENCE_LLM, "{0} should be evidence-LLM".format(element.id)

    @allure.story("Escalation scenario rubric")
    @allure.title("All four prose-quality elements carry EvidencePromptSpec checks with non-empty fields")
    def test_prose_elements_have_well_formed_specs(self):
        prose_elements = [element for element in ELEMENTS if element.id in _PROSE_ELEMENT_IDS]

        for element in prose_elements:
            assert isinstance(element.check, EvidencePromptSpec), element.id
            assert element.check.scenario_brief, "{0} has empty scenario_brief".format(element.id)
            assert element.check.question, "{0} has empty question".format(element.id)

    @allure.story("Escalation scenario rubric")
    @allure.title("narration_no_repetition covers all turns (evidence_turn is None) for cross-turn comparison")
    def test_repetition_element_covers_all_turns(self):
        repetition = next(element for element in ELEMENTS if element.id == "narration_no_repetition")

        assert isinstance(repetition.check, EvidencePromptSpec)
        assert repetition.check.evidence_turn is None

    @allure.story("Escalation scenario rubric")
    @allure.title("The three single-turn prose elements target the third assault turn (index 2)")
    def test_single_turn_prose_elements_target_climax(self):
        single_turn_ids = {"narration_no_cliches", "narration_no_purple_prose", "narration_no_invented_inner_states"}
        for element in ELEMENTS:
            if element.id not in single_turn_ids:
                continue
            assert isinstance(element.check, EvidencePromptSpec)
            assert element.check.evidence_turn == 2, "{0} should target turn 2 (third assault)".format(element.id)

    @allure.story("Escalation scenario rubric")
    @allure.title("All prose-quality elements have a positive base_value")
    def test_prose_elements_have_positive_base_value(self):
        prose_elements = [element for element in ELEMENTS if element.id in _PROSE_ELEMENT_IDS]

        for element in prose_elements:
            assert element.base_value > 0, "{0} has non-positive base_value".format(element.id)

    @allure.story("Escalation scenario rubric")
    @allure.title("Each prose-quality element is wired to its correct factory (not swapped with another)")
    def test_each_element_wired_to_correct_factory(self):
        factory_by_id = (
            ("narration_no_cliches", no_cliches),
            ("narration_no_purple_prose", no_purple_prose),
            ("narration_no_repetition", no_action_repetition),
            ("narration_no_invented_inner_states", no_invented_inner_states),
        )
        element_map = {element.id: element for element in ELEMENTS}
        for element_id, factory in factory_by_id:
            element = element_map[element_id]
            assert isinstance(element.check, EvidencePromptSpec)
            expected = factory(element.check.scenario_brief, evidence_turn=element.check.evidence_turn)
            assert element.check.question == expected.question, "{0} is wired to the wrong factory".format(element_id)
