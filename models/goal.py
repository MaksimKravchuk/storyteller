"""An NPC's autonomous goal — life-tier or tactical-tier.

NPCs carry up to two goals: a long-lived ``life_goal`` driven by
biography or world events (vengeance, ambition) and an ephemeral
``tactical_goal`` reacting to immediate stimuli (defend, eat, errand).
Both are :class:`Goal` instances differing only in :class:`GoalScope`.
The Actor sees the active goal in its prompt; ``cast.npc_turn`` advances
``turns_pursued`` and ``last_attempted_action`` after each tick; goal
completion flips both status and any matching ``WorldThread``.

Shape: pydantic ``BaseModel`` with string enums so values round-trip
through JSON for persistence.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

_PROGRESS_NOTE_LIMIT = 6


class GoalScope(str, Enum):
    """Whether a goal is value-driven (life) or situation-driven (tactical).

    ``LIFE`` goals persist across many scenes and are mutated only by
    completion or by the World Chronicler. ``TACTICAL`` goals live a
    handful of turns: a deterministic Director hook spawns them in
    response to player actions or when an NPC encounters their
    life-goal target, and a TTL retires them.
    """

    LIFE = "life"
    TACTICAL = "tactical"


class GoalKind(str, Enum):
    """Coarse classification of what the NPC is trying to do.

    The first five kinds (KILL, PURSUE, ACQUIRE, PROTECT, FLEE) are the
    historical life-tier set; the rest are tactical-tier additions used
    by the deterministic generator and may also be assigned by an Actor
    as a per-turn intent.
    """

    KILL = "kill"
    PURSUE = "pursue"
    ACQUIRE = "acquire"
    PROTECT = "protect"
    FLEE = "flee"
    DEFEND = "defend"
    EAT = "eat"
    ERRAND = "errand"
    REST = "rest"
    FLEE_SCENE = "flee_scene"


class GoalStatus(str, Enum):
    """Lifecycle states of an NPC goal.

    ``BLOCKED`` is set when a pursuer cannot physically reach the target
    (jail, exile). ``ABANDONED`` is set when circumstances make the goal
    moot (target left the city, reconciled). The World Chronicler emits
    both via ``GoalUpdate``; tactical goals also auto-ABANDON when their
    TTL expires.
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

    scope: GoalScope = GoalScope.LIFE
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
