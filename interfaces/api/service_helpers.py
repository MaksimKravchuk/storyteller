"""Projection helpers for ``interfaces.api.service``.

Split out so the public service module stays under wemake's
``WPS202 too many module members`` cap.
"""

from __future__ import annotations

from interfaces.api.schemas import SessionState, SessionSummary, TranscriptEntry
from interfaces.api.sessions import SessionEntry

_TRANSCRIPT_TAIL = 20


def entry_to_state(entry: SessionEntry) -> SessionState:
    """Build the full ``SessionState`` payload for one session."""
    state, _, _ = entry.engine.assert_running()
    return SessionState(
        session_id=entry.session_id,
        setting=entry.setting,
        language=entry.language,
        turn_count=state.turn_count,
        scene_description=_scene_description(state),
        inventory=list(state.player.inventory),
        recent_transcript=_recent_transcript(entry),
        created_at=entry.created_at,
    )


def entry_to_summary(entry: SessionEntry) -> SessionSummary:
    """Build the compact ``SessionSummary`` payload for the list endpoint."""
    state, _, _ = entry.engine.assert_running()
    return SessionSummary(
        session_id=entry.session_id,
        setting=entry.setting,
        language=entry.language,
        turn_count=state.turn_count,
        created_at=entry.created_at,
    )


def _scene_description(state) -> str:  # type: ignore[no-untyped-def]
    """Return ``current_scene.description`` if a scene is set, else an empty string."""
    scene = state.current_scene
    if scene is None:
        return ""
    return scene.description


def _recent_transcript(entry: SessionEntry) -> list[TranscriptEntry]:
    """Project the tail of ``entry.transcript`` into wire-side TranscriptEntry rows."""
    rows: list[TranscriptEntry] = []
    for turn in entry.transcript[-_TRANSCRIPT_TAIL:]:
        rows.append(TranscriptEntry(role=turn["role"], text=turn["text"]))
    return rows
