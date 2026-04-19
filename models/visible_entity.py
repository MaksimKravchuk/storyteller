"""Typed descriptor for a single player-visible entity in a scene.

A ``VisibleEntity`` is the payload the UI renders as an interactive chip
and the post-match step uses to wrap entity spans in narrator prose. It
carries the list of player-visible aliases rather than a single label —
the Narrator may alternate between them for natural prose and the
post-match wraps any of them as a hit for the same ``id``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, field_validator

VisibleEntityKind = Literal["npc", "poi", "item"]


class VisibleEntity(BaseModel):
    """One addressable entity currently visible to the player."""

    kind: VisibleEntityKind
    id: str
    names: list[str]

    @property
    def primary_name(self) -> str:
        """Return the first alias — used anywhere a single label is needed."""
        return self.names[0]

    @field_validator("names")
    @classmethod
    def _names_non_empty(cls, raw: list[str]) -> list[str]:
        stripped = [name.strip() for name in raw if name and name.strip()]
        if not stripped:
            raise ValueError("VisibleEntity.names must contain at least one non-empty name")
        return stripped
