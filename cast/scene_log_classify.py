"""Significance classification for :class:`SceneActionEntry`.

Lives outside :mod:`cast.scene_log` so the public append API stays
inside the WPS module-members budget. Rule-based for v1: combat,
intimidation wins, witnessed events, and aggressive player actions
become individual long-term memory nodes at scene end; routine
TALK / IDLE / MOVE / EXPLORE / LOOK / WAIT do not.
"""

from __future__ import annotations

from typing import Any

from models.scene_action_log import ActorKind

# Action types that never become individual memory nodes — pure scene
# texture, present in the prompt history but skipped by Phase 2 of
# scene-end consolidation.
_ROUTINE_ACTION_TYPES: frozenset[str] = frozenset(
    ("TALK", "IDLE", "MOVE", "EXPLORE", "LOOK", "WAIT", "PLAYER_INPUT"),
)

# NPC action types that are always significant when carried out.
_SIGNIFICANT_NPC_ACTION_TYPES: frozenset[str] = frozenset(("ATTACK",))

_INTIMIDATION_WIN_OUTCOMES: frozenset[str] = frozenset(("actor_succeeds", "actor_dominates"))


def _is_intimidation_win(action_type: str, metadata: dict[str, Any]) -> bool:
    """Return True for a successful INTIMIDATE — actor-side win."""
    if action_type != "INTIMIDATE":
        return False
    outcome = metadata.get("contest_outcome")
    return outcome in _INTIMIDATION_WIN_OUTCOMES


def classify_significance(
    actor_kind: ActorKind,
    action_type: str,
    metadata: dict[str, Any],
) -> bool:
    """Decide whether an entry should also become an individual memory node."""
    if action_type in _ROUTINE_ACTION_TYPES:
        return False
    if actor_kind == ActorKind.EVENT:
        return True
    if actor_kind == ActorKind.NPC and action_type in _SIGNIFICANT_NPC_ACTION_TYPES:
        return True
    if metadata.get("player_is_aggressive"):
        return True
    return _is_intimidation_win(action_type, metadata)
