"""Schema for the Scene Builder LLM JSON response."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PointOfInterestResponse(BaseModel):
    """Head-noun aliases the LLM may carry for a point of interest.

    The union branch exists so scene-response JSON can carry
    ``{"names": [...]}`` dicts alongside bare strings. A free-form
    ``dict[str, Any]`` branch would emit a JSON-Schema ``type: object``
    with unconstrained ``additionalProperties`` — strict mode rejects
    that because ``_StrictSchemaNormalizer`` can only clamp nodes that
    expose explicit ``properties``.
    """

    names: list[str] = Field(default_factory=list)


class SceneResponse(BaseModel):
    """Typed view of the Scene Builder LLM response.

    ``npcs_present`` entries are raw role strings. ``points_of_interest``
    entries are either bare strings (legacy) or :class:`PointOfInterestResponse`
    values carrying head-noun aliases. Coercion to ``SceneNPC`` /
    ``PointOfInterest`` happens in the SceneBuilder.
    """

    location_id: str = "unknown"
    description: str = ""
    npcs_present: list[str] = Field(default_factory=list)
    points_of_interest: list[str | PointOfInterestResponse] = Field(default_factory=list)
    ambient_description: str = ""
    time_of_day: str | None = None
