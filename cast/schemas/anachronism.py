"""Schema for the anachronism classifier LLM JSON response."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AnachronismAssessment(BaseModel):
    """Typed classifier output for a player action seen through a setting worldview."""

    strangeness_score: int = Field(
        default=0,
        ge=0,
        le=10,
        description="How strange the setting's inhabitants perceive the action or concepts, from 0 to 10.",
    )
    unfamiliar_concepts: list[str] = Field(
        default_factory=list,
        description="Canonical concept identifiers unfamiliar to the setting, empty when none apply.",
    )
    perceived_rewrite: str = Field(
        default="",
        description="How inhabitants would describe the action using their own worldview, empty if unnecessary.",
    )
