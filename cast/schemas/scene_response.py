"""Schema for the Scene Builder LLM JSON response."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SceneResponse(BaseModel):
    """Typed view of the Scene Builder LLM response.

    ``npcs_present`` entries are raw role strings. ``points_of_interest``
    entries are either bare strings (legacy) or
    ``{"names": [...]}`` dicts carrying head-noun aliases. Coercion to
    ``SceneNPC`` / ``PointOfInterest`` happens in the SceneBuilder.
    """

    location_id: str = "unknown"
    description: str = ""
    npcs_present: list[str] = Field(default_factory=list)
    points_of_interest: list[str | dict[str, Any]] = Field(default_factory=list)
    ambient_description: str = ""
    time_of_day: str | None = None
