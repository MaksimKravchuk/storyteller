"""Sentinel for a scene the Scene Builder could not match to a known place.

:func:`cast.scene_place.resolve_scene_location_id` maps every value that is
not a known place id — a fresh snake_case key, ``"unknown"`` or empty — to
this all-zero UUID; the Director then registers a new ``Location`` for it.
"""

from __future__ import annotations

from uuid import UUID

UNKNOWN_SCENE_LOCATION = UUID(int=0)
