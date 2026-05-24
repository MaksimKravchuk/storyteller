"""Pydantic request/response models for beta feedback."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

_FEEDBACK_MAX_CHARS = 4000


class FeedbackRequest(BaseModel):
    """Body for ``POST /api/games/{game_id}/feedback``."""

    category: Literal["bug", "confusing", "idea", "praise", "other"]
    message: str = Field(min_length=1, max_length=_FEEDBACK_MAX_CHARS)

    @field_validator("message", mode="before")
    @classmethod
    def strip_message(cls, raw_message: object) -> object:
        """Normalise direct API submissions before persistence."""
        return raw_message.strip() if isinstance(raw_message, str) else raw_message


class FeedbackResponse(BaseModel):
    """Acknowledgement for stored beta feedback."""

    feedback_id: str
