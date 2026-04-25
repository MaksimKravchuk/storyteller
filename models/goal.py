"""An NPC's persistent autonomous goal.

NPCs that hold a ``Goal`` carry it across turns: the Actor sees its
description and progress, ``cast.npc_turn`` updates ``turns_pursued``
and ``last_attempted_action`` after each tick, and goal completion
flips both this object's status and the matching ``WorldThread``.

Shape: pydantic ``BaseModel`` with string enums so values round-trip
through JSON for persistence.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

_PROGRESS_NOTE_LIMIT = 6


class GoalKind(str, Enum):
    """Coarse classification of what the NPC is trying to do."""

    KILL = "kill"
    PURSUE = "pursue"
    ACQUIRE = "acquire"
    PROTECT = "protect"
    FLEE = "flee"


class GoalStatus(str, Enum):
    """Lifecycle states of an NPC goal.

    ``BLOCKED`` is reserved for future Actor-driven goal mutation; this
    module never sets it. ``ABANDONED`` is set externally when a target
    becomes unreachable (e.g. the actor moves to another city).
    """

    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"
    BLOCKED = "blocked"


class Goal(BaseModel):
    """A standing intention the NPC pursues across turns.

    ``progress_notes`` is bounded — appending more than
    ``_PROGRESS_NOTE_LIMIT`` entries via :meth:`record_progress` drops
    the oldest, so the prompt budget stays predictable on long sessions.
    """

    kind: GoalKind
    description: str
    target_uuid: str | None = None
    status: GoalStatus = GoalStatus.ACTIVE
    turns_pursued: int = 0
    last_attempted_action: str | None = None
    progress_notes: list[str] = Field(default_factory=list)

    def record_progress(self, note: str) -> None:
        """Append a short retrospective, dropping the oldest note when over budget.

        Bumping ``turns_pursued`` is the caller's job — keeping it
        outside this method avoids a pydantic field-rebind that the
        WPS linter flags as class-attribute shadowing.
        """
        self.progress_notes.append(note)
        overflow = len(self.progress_notes) - _PROGRESS_NOTE_LIMIT
        for _ in range(max(overflow, 0)):
            self.progress_notes.pop(0)
