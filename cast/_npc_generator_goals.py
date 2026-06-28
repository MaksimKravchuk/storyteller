"""Goal-emission helpers for the NPC Generator.

Houses the goal-related slice of :mod:`cast.npc_generator`'s logic
(candidate-target listing, target-name resolution, draft → :class:`Goal`
conversion, kind allow-list) so the generator module stays inside its
WPS202 module-member budget. The generator imports the public helpers
back when it applies a per-batch rate-limited goal to a freshly built
``NPCCard``.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from loguru import logger

from cast.schemas.npc_response import NPCGoalDraft
from models.goal import Goal, GoalKind, GoalScope

# Life-tier kinds the LLM is allowed to assign at NPC creation: the
# combat/protective standing kinds plus the social/economic standing
# kinds (befriend, court, gossip, trade, help, warn, ask). Tactical
# kinds (DEFEND, EAT, ERRAND, REST, FLEE_SCENE) and ACQUIRE / FLEE are
# intentionally excluded — the prompt restraint clause asks for
# biography-driven standing intent only, and a fresh card carrying
# "FLEE" or "EAT" makes no narrative sense. AVOID is likewise excluded:
# it is a reactive stance the Chronicler assigns at runtime, never a
# motivation an NPC is born carrying. This frozenset must list exactly
# the kinds the generator prompt literal advertises (prompts/
# npc_generator_prompts.py) — a wider prompt silently drops drafts here,
# a wider frozenset is never produced by the LLM.
_GENERATOR_LIFE_GOAL_KINDS: frozenset[GoalKind] = frozenset(
    (
        GoalKind.KILL,
        GoalKind.PURSUE,
        GoalKind.ACQUIRE,
        GoalKind.PROTECT,
        GoalKind.BEFRIEND,
        GoalKind.COURT,
        GoalKind.GOSSIP,
        GoalKind.TRADE,
        GoalKind.HELP,
        GoalKind.WARN,
        GoalKind.ASK,
    ),
)


def candidate_goal_targets(game_state: Any) -> list[str]:
    """Return registered NPC names — the universe of valid ``goal.target_name`` values.

    Scene-only filtering would be too narrow: a vengeful NPC's antagonist
    may be elsewhere in the city today and still be a legitimate target.
    Capping the list here keeps the prompt budget bounded; the applier
    re-checks the resolved name against ``game_state.npcs``.
    """
    return [npc.name for npc in game_state.npcs.values() if npc.name]


def _resolve_target_uuid(target_name: str | None, game_state: Any) -> UUID | None:
    """Case-insensitive lookup of an NPC by display name; ``None`` when no match."""
    if not target_name:
        return None
    lowered = target_name.strip().lower()
    if not lowered:
        return None
    for npc in game_state.npcs.values():
        if npc.name and npc.name.lower() == lowered:
            return npc.uuid
    return None


def build_life_goal(draft: NPCGoalDraft, game_state: Any, npc_request: str) -> Goal | None:
    """Convert a validated ``NPCGoalDraft`` into a :class:`Goal`, or ``None`` to skip.

    Drops the goal when the kind is not in :data:`_GENERATOR_LIFE_GOAL_KINDS`
    or the target name does not resolve to a registered NPC. Both failure
    modes log at ``warning`` because a sustained miss-rate signals a
    prompt regression worth investigating.
    """
    if draft.kind not in _GENERATOR_LIFE_GOAL_KINDS:
        logger.warning(
            "NPCGenerator: dropping goal of kind '{0}' for role '{1}' (not allowed at creation)",
            draft.kind.value,
            npc_request,
        )
        return None
    target_uuid = _resolve_target_uuid(draft.target_name, game_state)
    if draft.target_name and target_uuid is None:
        logger.warning(
            "NPCGenerator: goal for role '{0}' targets '{1}' which does not match any NPC; dropping",
            npc_request,
            draft.target_name,
        )
        return None
    return Goal(
        scope=GoalScope.LIFE,
        kind=draft.kind,
        description=draft.description,
        target_uuid=target_uuid,
    )
