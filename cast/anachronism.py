"""Anachronism classifier performer substrate."""

from __future__ import annotations

from typing import Any

from cast.base_performer_class import BasePerformer
from cast.schemas.anachronism import AnachronismAssessment
from models.game_state import GameState
from prompts.anachronism_classifier import get_anachronism_classifier_prompts

SEED_CONCEPT_IDENTIFIERS: tuple[str, ...] = (
    "smartphone",
    "computer",
    "internet",
    "gps",
    "camera",
    "photograph",
    "video_recording",
    "electric_light",
    "battery",
    "radio",
    "television",
    "telephone",
    "automobile",
    "airplane",
    "train",
    "firearm",
    "plastic",
    "synthetic_fabric",
    "antibiotic",
    "vaccine",
    "anesthesia",
    "germ_theory",
    "electricity",
    "industrial_machine",
    "credit_card",
    "paper_money",
    "passport",
    "modern_democracy",
    "gender_equality",
    "digital_map",
)

_DEFAULT_SETTING_DETAIL = "unknown"


def _join_setting_list(setting_values: list[str]) -> str:
    """Render setting list fields for compact prompt context."""
    if not setting_values:
        return _DEFAULT_SETTING_DETAIL
    return ", ".join(setting_values)


class AnachronismClassifier(BasePerformer):
    """Classify how an action from a player's origin era reads in the target setting."""

    def __init__(self, *, llm_client: Any, language: str = "English"):
        prompts = get_anachronism_classifier_prompts(language)
        super().__init__(
            llm_client=llm_client,
            system_prompt_template=prompts.system,
        )
        self._review_template = prompts.review
        self.set_context(seed_concepts=", ".join(SEED_CONCEPT_IDENTIFIERS))

    async def act(self, input_data: str, context: dict) -> AnachronismAssessment:
        """Return a structured anachronism assessment for ``input_data``.

        The substrate is opt-in. Without an ``origin_era`` in context, it
        returns a neutral assessment and avoids an LLM call so existing game
        flow remains unchanged until a caller deliberately supplies one.
        """
        origin_era = str(context.get("origin_era", "")).strip()
        player_action = str(input_data or context.get("player_action", "")).strip()
        if not origin_era or not player_action:
            return AnachronismAssessment()
        game_state: GameState = context["game_state"]
        self._sync_setting_context(game_state, origin_era)
        return await self._send_json(
            self._review_template.format(player_action=player_action),
            response_model=AnachronismAssessment,
        )

    def _sync_setting_context(self, game_state: GameState, origin_era: str) -> None:
        """Copy current setting fields into prompt variables."""
        setting = game_state.setting
        self.set_context(
            origin_era=origin_era,
            setting_name=setting.name,
            time_period=setting.time_period,
            setting_technologies=_join_setting_list(setting.technologies),
            social_structure=setting.social_structure or _DEFAULT_SETTING_DETAIL,
        )
