"""Typed relationship model replacing the old dict[str, str] encoding."""

from __future__ import annotations

import logging
from enum import StrEnum

from pydantic import Field, field_validator

from models.base_model import StorytellerBase

_log = logging.getLogger(__name__)


class RelationshipKind(StrEnum):
    ALLY = "ally"
    FRIEND = "friend"
    NEUTRAL = "neutral"
    RIVAL = "rival"
    ENEMY = "enemy"
    KIN = "kin"
    SUBORDINATE = "subordinate"
    SUPERIOR = "superior"


class Relationship(StorytellerBase):
    """A directed relationship from one character to another.

    ``target_uuid`` references the NPC this relationship is about.
    ``kind`` is the semantic category; ``intensity`` is a signed
    -3..+3 modifier (negative = hostile, positive = warm).
    ``note`` carries narrative colour and is never parsed programmatically.
    """

    target_uuid: str
    kind: RelationshipKind
    intensity: int = Field(default=0, ge=-3, le=3)
    note: str = ""
    established_turn: int | None = None
    source_thread_uuid: str | None = None

    @field_validator("kind", mode="before")
    @classmethod
    def coerce_kind(cls, raw_kind: object) -> object:
        if isinstance(raw_kind, str):
            coerced = raw_kind.strip().lower()
            try:
                return RelationshipKind(coerced)
            except ValueError:
                _log.warning("Unknown relationship kind %r, defaulting to neutral", raw_kind)
                return RelationshipKind.NEUTRAL
        return raw_kind
