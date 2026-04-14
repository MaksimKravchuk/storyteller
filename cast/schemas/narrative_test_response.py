"""Schema for the Narrative Test Agent LLM JSON response.

The Narrative Test Agent is a higher-tier QA reviewer that audits the
game's narrative output across six dimensions. Its response is a
:class:`NarrativeEvaluation` — a deterministic envelope that carries a
:class:`DimensionScore` for each dimension plus an overall mean and a
short summary. The schema participates in the validation-retry loop in
:meth:`cast.base_performer_class.BasePerformer._send_json`, so malformed
replies are self-corrected before bubbling up to the caller.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

_MIN_DIMENSION_SCORE = 1
_MAX_DIMENSION_SCORE = 10
_MIN_OVERALL_SCORE = float(_MIN_DIMENSION_SCORE)
_MAX_OVERALL_SCORE = float(_MAX_DIMENSION_SCORE)


class DimensionScore(BaseModel):
    """Per-dimension QA verdict.

    ``score`` is a 1-10 integer with the rubric documented in
    :data:`prompts.narrative_test_prompts.NARRATIVE_TEST_SYSTEM`.
    The three list fields must quote concrete details from the audited
    transcript — the agent is instructed to never emit generic platitudes.
    """

    score: int = Field(ge=_MIN_DIMENSION_SCORE, le=_MAX_DIMENSION_SCORE)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class NarrativeEvaluation(BaseModel):
    """Full narrative audit covering six dimensions of the game.

    The dimensions mirror the Storyteller architecture:

    - ``story`` — overall narrative coherence across turns.
    - ``turns`` — per-turn pacing and cause/effect clarity.
    - ``scenes`` — Scene Builder output quality and atmosphere.
    - ``confrontation`` — dice/combat stakes and honest consequences.
    - ``memory`` — NPC and world recall of earlier interactions.
    - ``autonomy`` — how alive the world feels offscreen.

    ``overall_score`` is the arithmetic mean of the six dimension scores
    rounded to one decimal. ``summary`` is a 2-4 sentence digest of the
    top finding in each dimension.
    """

    story: DimensionScore
    turns: DimensionScore
    scenes: DimensionScore
    confrontation: DimensionScore
    memory: DimensionScore
    autonomy: DimensionScore
    overall_score: float = Field(ge=_MIN_OVERALL_SCORE, le=_MAX_OVERALL_SCORE)
    summary: str
