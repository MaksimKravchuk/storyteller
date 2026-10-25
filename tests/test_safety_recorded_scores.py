"""Default moderation decisions on real omni-moderation scores for ordinary game turns.

Hand-picked scores in the other safety tests let plain violence (a sword blow scores ~0.9)
block every fight. ``tests/fixtures/moderation_scores.json`` holds scores recorded from the
live endpoint; re-record with ``tests/fixtures/record_moderation_scores.py`` when the model changes.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import allure
import pytest

from safety.heuristic import HeuristicProvider
from safety.moderator import Moderator
from safety.openai_provider import severities_from_response
from safety.result import ModerationCategory, ModerationDirection, ModerationSeverity

pytestmark = [
    allure.epic("Engine & LLM Infrastructure"),
    allure.feature("Content safety"),
    allure.story("Recorded omni-moderation scores"),
]

_SAMPLES: list[dict[str, Any]] = json.loads(
    (Path(__file__).parent / "fixtures" / "moderation_scores.json").read_text(encoding="utf-8"),
)["samples"]


@dataclass
class _RecordedProvider:
    """Replays one recorded omni-moderation response through the real score mapping."""

    category_scores: Mapping[str, float]
    name: str = "openai"

    async def score(self, text: str) -> Mapping[ModerationCategory, ModerationSeverity]:
        return severities_from_response({"results": [{"category_scores": self.category_scores}]})


@allure.title("Default thresholds pass ordinary fights and block gore and self-harm on real scores")
@pytest.mark.asyncio
@pytest.mark.parametrize("sample", _SAMPLES, ids=[sample["text"][:40] for sample in _SAMPLES])
async def test_default_moderation_on_recorded_scores(sample: dict[str, Any]) -> None:
    # Same providers and default thresholds as safety.factory.build_moderator with an OpenAI key.
    moderator = Moderator(providers=[HeuristicProvider(), _RecordedProvider(sample["category_scores"])])
    moderation = await moderator.check(sample["text"], direction=ModerationDirection(sample["direction"]))
    assert moderation.flagged == (sample["expect"] == "block"), moderation.triggering_categories
