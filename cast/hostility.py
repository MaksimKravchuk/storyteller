"""Mechanical hostility tracking for NPCs under player aggression.

When the Director sees an aggressive player action, it calls
:func:`bump_hostility` on each targeted NPC *before* dialogue runs.
This bumps the NPC's ``hostility_level`` counter, appends an entry to
the ``recent_hostile_actions`` FIFO (capped at 3), and raises
``current_mood`` to the computed floor.

Together these remove the Actor prompt's reliance on the LLM remembering
to emit ``[MOOD: hostile]`` — the mood ratchet becomes deterministic.
The floor mapping is calibrated against
:data:`cast.dice.AGGRESSION_THRESHOLDS`: every non-zero hostility level
lands on a mood with an aggression threshold, so
:class:`cast.director_retaliation.RetaliationHandler` can fire.
"""

from __future__ import annotations

import types

from models.npc_card import NPCCard

_HISTORY_CAP = 3
_LEVEL_CAP = 10

SEVERITY_LOW = "low"
SEVERITY_HIGH = "high"

# Retaliation kicks in at this level — same threshold the Director uses
# to decide whether to un-skip a combat-engaged NPC from the retaliation
# phase. Keeping the constant here makes the calibration explicit.
RETALIATION_THRESHOLD = 3

_SEVERITY_BUMPS: types.MappingProxyType[str, int] = types.MappingProxyType(
    {
        SEVERITY_LOW: 1,
        SEVERITY_HIGH: 2,
    }
)

_MOOD_FLOOR_LADDER: tuple[tuple[int, str], ...] = (
    (9, "enraged"),
    (7, "hostile"),
    (5, "angry"),
    (3, "threatened"),
    (1, "irritated"),
)

_MOOD_INTENSITY: types.MappingProxyType[str, int] = types.MappingProxyType(
    {
        "neutral": 0,
        "happy": 0,
        "calm": 0,
        "content": 0,
        "suspicious": 1,
        "irritated": 2,
        "threatened": 3,
        "angry": 4,
        "hostile": 5,
        "furious": 6,
        "enraged": 7,
    }
)


def mood_floor(hostility_level: int) -> str | None:
    """Return the minimum mood for a given hostility level.

    Returns ``None`` for level 0 — no floor is imposed on peaceful NPCs,
    so a guard who has not yet been provoked keeps whatever mood the
    LLM or scene generator assigned.
    """
    for threshold, mood in _MOOD_FLOOR_LADDER:
        if hostility_level >= threshold:
            return mood
    return None


def bump_hostility(
    npc: NPCCard,
    *,
    turn: int,
    player_action: str,
    severity: str = SEVERITY_LOW,
) -> None:
    """Bump ``npc.hostility_level``, append to the FIFO history, raise mood.

    ``severity`` accepts :data:`SEVERITY_LOW` (+1) or :data:`SEVERITY_HIGH`
    (+2). Unknown values fall back to the low-severity bump so the
    counter still moves.

    Mutates the NPCCard in place. ``current_mood`` is only overwritten
    *upward* along the intensity ladder — if the LLM already pushed the
    mood past the computed floor, we leave it alone.
    """
    bump = _SEVERITY_BUMPS.get(severity, _SEVERITY_BUMPS[SEVERITY_LOW])
    npc.hostility_level = min(npc.hostility_level + bump, _LEVEL_CAP)

    history = list(npc.recent_hostile_actions)
    history.append(
        {
            "turn": str(turn),
            "action": player_action,
            "severity": severity,
        },
    )
    npc.recent_hostile_actions = history[-_HISTORY_CAP:]

    floor = mood_floor(npc.hostility_level)
    if floor is not None and _is_stronger_mood(floor, npc.current_mood):
        npc.current_mood = floor


def format_hostile_actions_summary(actions: list[dict[str, str]]) -> str:
    """Render recent hostile actions as a short bullet list for prompts.

    Empty input yields an empty string so callers can decide whether to
    inject the section at all.
    """
    if not actions:
        return ""
    lines = [_format_entry(entry) for entry in actions]
    return "\n".join(lines)


def apply_llm_mood_update(npc: NPCCard, new_mood: str) -> None:
    """Apply an LLM-emitted ``[MOOD:]`` tag with a mechanical-floor guard.

    When the NPC's ``hostility_level`` is 0 the LLM has free rein — it
    may freely de-escalate, shift sideways, or pick any label that fits
    the scene. Once hostility is engaged, we reject any label that
    would slide below the floor set by :func:`mood_floor`; without this
    guard, an inattentive LLM emitting ``[MOOD: calm]`` right after the
    Director has ratcheted the NPC up to ``threatened`` would defeat
    the retaliation path entirely.
    """
    floor = mood_floor(npc.hostility_level)
    if floor is not None and _is_stronger_mood(floor, new_mood):
        # LLM tried to de-escalate a mechanically-hostile NPC; keep the floor.
        return
    npc.current_mood = new_mood


def _format_entry(entry: dict[str, str]) -> str:
    turn = entry.get("turn", "?")
    action = entry.get("action", "")
    severity = entry.get("severity", SEVERITY_LOW)
    return "- Turn {0} ({1}): {2}".format(turn, severity, action)


def _is_stronger_mood(candidate: str, current: str) -> bool:
    """Report whether ``candidate`` outranks ``current`` on the hostility ladder.

    Unknown moods score as 0 (peaceful), so any hostile floor overrides
    an LLM-invented label like ``stoic`` or ``confused``.
    """
    candidate_score = _MOOD_INTENSITY.get(candidate.lower(), 0)
    current_score = _MOOD_INTENSITY.get(current.lower(), 0)
    return candidate_score > current_score
