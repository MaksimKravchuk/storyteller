"""Bystander mood-shift helpers for the autonomy scenario elements."""

from __future__ import annotations

from benchmarks.harness.snapshots import mood_of
from models.game_state import GameState

MoodNote = tuple[bool, str]


def guard_uuid_by_name(snap: GameState, name: str) -> str | None:
    """Resolve a guard's UUID from the snapshot."""
    target = name.strip().lower()
    for uuid, npc in snap.npcs.items():
        if npc.name.strip().lower() == target:
            return uuid
    return None


def _describe_shift(name: str, before_mood: str, after_mood: str) -> MoodNote:
    """Return ``(shifted, description)`` for one bystander's mood change."""
    if after_mood.strip().lower() == before_mood.strip().lower():
        return False, "{0}: stayed {1}".format(name, before_mood)
    return True, "{0}: {1} → {2}".format(name, before_mood, after_mood)


def bystander_mood_note(before: GameState, after: GameState, name: str) -> MoodNote | None:
    """Return one bystander's shift note, or ``None`` when the NPC is missing."""
    uuid = guard_uuid_by_name(before, name)
    if uuid is None:
        return None
    return _describe_shift(
        name,
        before_mood=mood_of(before, uuid) or "",
        after_mood=mood_of(after, uuid) or "",
    )


def summarise_mood_notes(notes: list[MoodNote]) -> tuple[int, str]:
    """Return ``(awarded_points, reason_text)`` for a list of bystander notes."""
    awarded = sum(1 for note in notes if note[0])
    details = "; ".join(note[1] for note in notes) or "no bystander moods inspected"
    return awarded, details


def score_bystander_moods(
    before: GameState,
    after: GameState,
    names: tuple[str, ...],
) -> tuple[int, str]:
    """Collect mood notes for each bystander and summarise to ``(awarded, reason)``."""
    raw = (bystander_mood_note(before, after, name) for name in names)
    return summarise_mood_notes([note for note in raw if note is not None])
