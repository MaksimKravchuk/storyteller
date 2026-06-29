"""Tests for the anachronism classifier substrate."""

from __future__ import annotations

from unittest.mock import AsyncMock

import allure
import pytest
from pydantic import ValidationError

from cast.anachronism import AnachronismClassifier, SEED_CONCEPT_IDENTIFIERS
from cast.schemas.anachronism import AnachronismAssessment
from knowledge.graph import KnowledgeGraph
from models.game_state import GameState
from models.setting import Setting
from prompts.anachronism_classifier import ANACHRONISM_CLASSIFIER_SYSTEM

_GAME_STATE = "game_state"
_ORIGIN_ERA = "origin_era"
_PLAYER_ACTION = "player_action"


def _make_game_state() -> GameState:
    return GameState(
        setting=Setting(
            name="Ancient Rome",
            time_period="1st century AD",
            region="Italy",
            summary="The Roman Empire under the early emperors.",
            technologies=["aqueducts", "wax tablets"],
            social_structure="senators, equites, plebs, freedmen, and enslaved people",
        ),
        knowledge_graph=KnowledgeGraph(),
    )


@allure.epic("Narrative Delivery")
@allure.feature("Anachronism classifier")
@allure.story("Schema validation")
class TestAnachronismAssessmentSchema:
    @allure.title("AnachronismAssessment accepts strangeness scores at both inclusive bounds")
    def test_score_bounds_are_inclusive(self) -> None:
        assert AnachronismAssessment(strangeness_score=0).strangeness_score == 0
        assert AnachronismAssessment(strangeness_score=10).strangeness_score == 10

    @allure.title("AnachronismAssessment rejects strangeness scores outside 0 through 10")
    @pytest.mark.parametrize("score", [-1, 11])
    def test_score_bounds_reject_out_of_range_values(self, score: int) -> None:
        with pytest.raises(ValidationError):
            AnachronismAssessment(strangeness_score=score)


@allure.epic("Narrative Delivery")
@allure.feature("Anachronism classifier")
@allure.story("Prompt contract")
class TestAnachronismPrompt:
    @allure.title("System prompt has worldview, setting, and action sections plus seed reuse guidance")
    def test_system_prompt_contains_required_sections(self) -> None:
        rendered = ANACHRONISM_CLASSIFIER_SYSTEM.render(
            origin_era="modern day",
            setting_name="Ancient Rome",
            time_period="1st century AD",
            setting_technologies="aqueducts, wax tablets",
            social_structure="senators and plebs",
            seed_concepts=", ".join(SEED_CONCEPT_IDENTIFIERS),
        )

        assert "WORLDVIEW" in rendered
        assert "SETTING" in rendered
        assert "ACTION" in rendered
        assert "reuse these seed identifiers" in rendered
        assert "smartphone" in rendered

    @allure.title("Canonical seed concepts contain roughly thirty stable snake-case identifiers")
    def test_seed_concepts_are_canonical_identifiers(self) -> None:
        assert 25 <= len(SEED_CONCEPT_IDENTIFIERS) <= 35
        assert "smartphone" in SEED_CONCEPT_IDENTIFIERS
        assert "electric_light" in SEED_CONCEPT_IDENTIFIERS
        assert all(identifier == identifier.lower() for identifier in SEED_CONCEPT_IDENTIFIERS)
        assert all(" " not in identifier for identifier in SEED_CONCEPT_IDENTIFIERS)


@allure.epic("Narrative Delivery")
@allure.feature("Anachronism classifier")
@allure.story("Async invocation")
class TestAnachronismClassifier:
    @allure.title("Classifier short-circuits to a neutral assessment when no origin era is supplied")
    @pytest.mark.asyncio
    async def test_no_origin_era_returns_neutral_without_llm(self) -> None:
        classifier = AnachronismClassifier(llm_client=AsyncMock())
        classifier._send_json = AsyncMock()  # type: ignore[method-assign]

        assessment = await classifier.execute(
            input_data="check the time on my phone",
            context={_GAME_STATE: _make_game_state()},
        )

        assert assessment == AnachronismAssessment()
        classifier._send_json.assert_not_called()  # type: ignore[attr-defined]

    @allure.title("Classifier can be invoked asynchronously and sends setting context to the LLM")
    @pytest.mark.asyncio
    async def test_classifier_invokes_llm_with_setting_context(self) -> None:
        expected = AnachronismAssessment(
            strangeness_score=9,
            unfamiliar_concepts=["smartphone"],
            perceived_rewrite="a glossy black talisman with no visible flame",
        )
        classifier = AnachronismClassifier(llm_client=AsyncMock())
        classifier._send_json = AsyncMock(return_value=expected)  # type: ignore[method-assign]

        result = await classifier.execute(
            input_data="unlock my smartphone and show them the map",
            context={
                _GAME_STATE: _make_game_state(),
                _ORIGIN_ERA: "modern day",
                _PLAYER_ACTION: "unlock my smartphone and show them the map",
            },
        )

        assert result == expected
        classifier._send_json.assert_awaited_once()  # type: ignore[attr-defined]
        await_args = classifier._send_json.await_args  # type: ignore[attr-defined]
        assert await_args is not None
        prompt = await_args.args[0]
        assert "unlock my smartphone" in prompt
        assert "modern day" in classifier._system_prompt_vars["origin_era"]
        assert "aqueducts" in classifier._system_prompt_vars["setting_technologies"]
        assert "senators" in classifier._system_prompt_vars["social_structure"]
