"""Schema for the Scene Builder LLM JSON response."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SceneResponse(BaseModel):
    """Typed view of the Scene Builder LLM response.

    ``npcs_present`` contains raw role strings from the LLM. The
    ``SceneBuilder.act()`` caller wraps each string in a ``SceneNPC``
    instance. ``time_of_day`` is optional; the caller falls back to
    ``game_state.game_time`` when the LLM omits it.
    """

    location_id: str = "unknown"
    description: str = ""
    npcs_present: list[str] = Field(default_factory=list)
    points_of_interest: list[str] = Field(default_factory=list)
    ambient_description: str = ""
    time_of_day: str | None = None
