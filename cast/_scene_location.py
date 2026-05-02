"""Coerce LLM-emitted scene location identifiers into ``uuid.UUID``.

The Scene Builder's JSON contract still allows the literal string
``"unknown"`` as a sentinel for "I could not match this scene to any
registered location". With ``Scene.location_id: UUID`` that sentinel
no longer round-trips through pydantic, so this module rewrites both
the empty default and the legacy ``"unknown"`` string into a stable
all-zero sentinel UUID before the Scene is constructed.
"""

from __future__ import annotations

from uuid import UUID

from loguru import logger

UNKNOWN_SCENE_LOCATION = UUID(int=0)


def coerce_scene_location_id(raw: str | UUID | None) -> UUID:
    """Resolve the LLM-emitted scene ``location_id`` into a real ``UUID``.

    Empty / ``"unknown"`` input is the documented "no known location"
    case and collapses silently. A non-empty unparseable string is a
    Scene Builder regression — it logs a warning so operators can
    distinguish "LLM said unknown" from "LLM hallucinated a label".
    """
    if isinstance(raw, UUID):
        return raw
    if not raw or raw == "unknown":
        return UNKNOWN_SCENE_LOCATION
    try:
        return UUID(raw)
    except ValueError:
        logger.warning(
            "_scene_location.coerce_scene_location_id: location_id={0!r} unparseable, collapsed to sentinel",
            raw,
        )
        return UNKNOWN_SCENE_LOCATION
