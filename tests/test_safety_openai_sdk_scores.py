"""OpenAI moderation categories are read from the real SDK response object.

The SDK's pydantic fields are ``sexual_minors`` / ``self_harm``; the provider's
category map is keyed by the wire names (``sexual/minors``). Plain-dict
fixtures never exercise that gap, so this test builds the SDK model itself.
"""

from __future__ import annotations

from types import SimpleNamespace

import allure
from openai.types.moderation import CategoryScores

from safety.openai_provider import severities_from_response
from safety.result import ModerationCategory, ModerationSeverity

pytestmark = [
    allure.epic("Engine & LLM Infrastructure"),
    allure.feature("Content safety"),
    allure.story("OpenAI provider"),
]


def _sdk_response(wire_scores: dict[str, float]) -> SimpleNamespace:
    scores: dict[str, float] = {(spec.alias or name): 0 for name, spec in CategoryScores.model_fields.items()}
    scores.update(wire_scores)
    return SimpleNamespace(results=[SimpleNamespace(category_scores=CategoryScores.model_validate(scores))])


@allure.title("severities_from_response enforces sexual/minors and self-harm on the real OpenAI SDK object")
def test_slash_and_hyphen_categories_are_enforced() -> None:
    severities = severities_from_response(_sdk_response({"sexual/minors": 0.95, "self-harm/intent": 0.6}))

    assert severities[ModerationCategory.SEXUAL_MINORS] == ModerationSeverity.HIGH
    assert severities[ModerationCategory.SELF_HARM] == ModerationSeverity.MEDIUM
