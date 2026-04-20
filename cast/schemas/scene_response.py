"""Schema for the Scene Builder LLM JSON response."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SceneResponse(BaseModel):
    """Typed view of the Scene Builder LLM response.

    ``npcs_present`` contains raw role strings from the LLM. The
    ``SceneBuilder.act()`` caller wraps each string in a ``SceneNPC``
    instance. ``time_of_day`` is optional; the caller falls back to
    ``game_state.game_time`` when the LLM omits it.

    ``points_of_interest`` entries are either bare strings (legacy
    shape, still accepted for robustness) or dicts of the form
    ``{"names": ["primary phrase", "short head", ...]}`` — the richer
    form carries head-noun aliases that the entity-markup post-match
    can hit even when the Narrator informally abbreviates the primary
    phrase. Coercion to :class:`models.scene.PointOfInterest` happens
    in ``SceneBuilder._scene_from_response`` via the shared helper.
    """

    location_id: str = "unknown"
    description: str = ""
    npcs_present: list[str] = Field(default_factory=list)
    points_of_interest: list[str | dict[str, Any]] = Field(default_factory=list)
    ambient_description: str = ""
    time_of_day: str | None = None
