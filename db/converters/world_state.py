"""WorldState ↔ JSONB dict converters.

The whole living-world state lives as a single JSONB blob on the
``game_states`` row, so we serialise it via ``dataclasses.asdict`` and
rehydrate it by walking the nested dicts. Legacy rows where
``world_state`` is ``NULL`` deserialise to a fresh empty
:class:`WorldState`.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, cast

from models.world_state import ThreadCategory, ThreadStatus, WorldState, WorldThread

_UUID_KEY = "uuid"

_VALID_THREAD_CATEGORIES: frozenset[str] = frozenset(
    ("personal", "political", "natural", "economic", "social", "cultural"),
)
_VALID_THREAD_STATUSES: frozenset[str] = frozenset(("open", "resolved", "abandoned"))


def world_state_to_dict(state: WorldState) -> dict[str, Any]:
    """Serialise a :class:`WorldState` into a JSON-ready dict."""
    return asdict(state)


def dict_to_world_state(payload: dict[str, Any] | None) -> WorldState:
    """Rehydrate a :class:`WorldState` from a JSONB payload.

    ``None`` (legacy rows) and empty dicts both yield a fresh
    :class:`WorldState` with default values.
    """
    if not payload:
        return WorldState()

    threads = [_dict_to_thread(raw_thread) for raw_thread in payload.get("threads", [])]
    state = WorldState(
        threads=threads,
        world_mood=payload.get("world_mood"),
        last_chronicled_scene=payload.get("last_chronicled_scene", 0),
    )
    stored_uuid = payload.get(_UUID_KEY)
    if stored_uuid is not None:
        state.uuid = stored_uuid
    return state


def _dict_to_thread(raw: dict[str, Any]) -> WorldThread:
    thread = WorldThread(
        description=raw["description"],
        category=_coerce_thread_category(raw["category"]),
        introduced_scene=raw["introduced_scene"],
        involved_locations=list(raw.get("involved_locations", [])),
        involved_npcs=list(raw.get("involved_npcs", [])),
        status=_coerce_thread_status(raw.get("status", "open")),
        last_advanced_scene=raw.get("last_advanced_scene", 0),
    )
    stored_uuid = raw.get(_UUID_KEY)
    if stored_uuid is not None:
        thread.uuid = stored_uuid
    return thread


def _coerce_thread_category(raw_category: str) -> ThreadCategory:
    if raw_category not in _VALID_THREAD_CATEGORIES:
        raise ValueError(f"Unknown thread category: {raw_category!r}")
    return cast(ThreadCategory, raw_category)


def _coerce_thread_status(raw_status: str) -> ThreadStatus:
    if raw_status not in _VALID_THREAD_STATUSES:
        raise ValueError(f"Unknown thread status: {raw_status!r}")
    return cast(ThreadStatus, raw_status)
