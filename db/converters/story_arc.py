"""StoryArc ↔ JSONB dict converters.

The whole arc lives as a single JSONB blob on the ``game_states`` row,
so we serialise it via ``dataclasses.asdict`` and rehydrate it by
walking the nested dicts. Legacy rows where ``story_arc`` is ``NULL``
deserialise to a fresh empty :class:`StoryArc`.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, cast

from models.story_arc import Beat, BeatKind, PlotThread, StoryArc, ThreadStatus

_UUID_KEY = "uuid"

_VALID_BEAT_KINDS: frozenset[str] = frozenset(("setup", "rising", "climax", "falling", "resolution"))
_VALID_THREAD_STATUSES: frozenset[str] = frozenset(("open", "resolved", "abandoned"))


def story_arc_to_dict(arc: StoryArc) -> dict[str, Any]:
    """Serialise a :class:`StoryArc` into a JSON-ready dict."""
    return asdict(arc)


def dict_to_story_arc(payload: dict[str, Any] | None) -> StoryArc:
    """Rehydrate a :class:`StoryArc` from a JSONB payload.

    ``None`` (legacy rows) and empty dicts both yield a fresh
    :class:`StoryArc` with default values.
    """
    if not payload:
        return StoryArc()

    beats = [_dict_to_beat(raw_beat) for raw_beat in payload.get("beats", [])]
    threads = [_dict_to_thread(raw_thread) for raw_thread in payload.get("threads", [])]
    arc = StoryArc(
        act=payload.get("act", 1),
        current_beat_id=payload.get("current_beat_id"),
        beats=beats,
        threads=threads,
    )
    stored_uuid = payload.get(_UUID_KEY)
    if stored_uuid is not None:
        arc.uuid = stored_uuid
    return arc


def _dict_to_beat(raw: dict[str, Any]) -> Beat:
    beat = Beat(
        description=raw["description"],
        kind=_coerce_beat_kind(raw["kind"]),
        resolved=raw.get("resolved", False),
    )
    stored_uuid = raw.get(_UUID_KEY)
    if stored_uuid is not None:
        beat.uuid = stored_uuid
    return beat


def _dict_to_thread(raw: dict[str, Any]) -> PlotThread:
    thread = PlotThread(
        description=raw["description"],
        introduced_scene=raw["introduced_scene"],
        involved_npcs=list(raw.get("involved_npcs", [])),
        status=_coerce_thread_status(raw.get("status", "open")),
    )
    stored_uuid = raw.get(_UUID_KEY)
    if stored_uuid is not None:
        thread.uuid = stored_uuid
    return thread


def _coerce_beat_kind(raw_kind: str) -> BeatKind:
    if raw_kind not in _VALID_BEAT_KINDS:
        raise ValueError(f"Unknown beat kind: {raw_kind!r}")
    return cast(BeatKind, raw_kind)


def _coerce_thread_status(raw_status: str) -> ThreadStatus:
    if raw_status not in _VALID_THREAD_STATUSES:
        raise ValueError(f"Unknown thread status: {raw_status!r}")
    return cast(ThreadStatus, raw_status)
