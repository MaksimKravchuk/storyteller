"""LLM judge for full-session narrative quality."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from llm.message import Message, OutputFormat, Role
from tests.e2e._real_llm import real_llm_for
from tests.e2e.narrative_report import NarrativeReport, RubricScore
from tests.e2e.session_transcript import SessionTranscript

RUBRICS: tuple[str, ...] = (
    "Story continuity",
    "Player agency",
    "NPC believability",
    "World consistency",
    "Prose quality",
    "Action consequence clarity",
)

_MIN_SCORE = 1
_MAX_SCORE = 10
_JSON_FORMAT = OutputFormat(response_format={"type": "json_object"})
_SYSTEM_PROMPT = "You are a strict QA judge for interactive fiction transcripts. Return only JSON."


class NarrativeTestAgent:
    """Grade a transcript across narrative-quality rubrics using a live model."""

    def __init__(self) -> None:
        self._client = real_llm_for("narrator")
        self.model = self._client.model

    async def evaluate(self, transcript: SessionTranscript, rubric: str) -> RubricScore:
        """Return one rubric score for ``transcript``."""
        response = await self._client.send_message(
            messages=[Message(role=Role.USER, body=_build_user_prompt(transcript, rubric))],
            system_prompt=_SYSTEM_PROMPT,
            output_format=_JSON_FORMAT,
        )
        payload = _parse_json_object(response.body)
        score = _coerce_score(payload.get("score"))
        return RubricScore(
            rubric=rubric,
            score=score,
            reasoning=str(payload.get("reasoning") or ""),
            issues=tuple(str(issue) for issue in payload.get("issues") or ()),
        )

    async def evaluate_session(self, transcript: SessionTranscript) -> NarrativeReport:
        """Evaluate every rubric and return an aggregate report."""
        scores = await asyncio.gather(*self._evaluation_tasks(transcript))
        return NarrativeReport(model=self.model, scores=tuple(scores))

    def _evaluation_tasks(self, transcript: SessionTranscript):
        return [self.evaluate(transcript, rubric) for rubric in RUBRICS]


def _build_user_prompt(transcript: SessionTranscript, rubric: str) -> str:
    return "\n".join(
        [
            f"Rubric: {rubric}",
            "",
            "Score the transcript from 1 to 10 for this rubric.",
            "Return JSON with keys: score (integer), reasoning (string), issues (array of strings).",
            "Be concise and cite concrete transcript evidence.",
            "",
            transcript.render(),
        ],
    )


def _parse_json_object(raw_body: str) -> dict[str, Any]:
    stripped = raw_body.strip()
    if stripped.startswith("```"):
        stripped = _strip_fence(stripped)
    parsed = json.loads(stripped)
    if not isinstance(parsed, dict):
        raise TypeError("Narrative judge returned non-object JSON")
    return parsed


def _strip_fence(raw_body: str) -> str:
    lines = raw_body.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _coerce_score(raw_score: Any) -> int:
    score = int(raw_score)
    if not _MIN_SCORE <= score <= _MAX_SCORE:
        raise ValueError(f"Narrative judge score out of range: {score}")
    return score
