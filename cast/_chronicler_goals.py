"""Apply Chronicler-emitted goal drafts and updates to NPCCards.

Pure helpers extracted from :mod:`cast.director_execution` so the
plan-executor module stays inside its WPS budgets. Both public
functions are idempotent in the absence of new input and skip drafts
that reference unknown UUIDs (the chronicler must never invent NPCs
out of thin air).
"""

from __future__ import annotations

import types
from collections.abc import Mapping
from uuid import UUID

from loguru import logger

from cast.schemas.chronicler_response import GoalDraft, GoalUpdate
from models.goal import Goal, GoalScope, GoalStatus
from models.npc_card import NPCCard

# Status names the Chronicler may emit. ``MappingProxyType`` keeps it
# immutable, satisfying WPS407 without a private wrapper.
_STATUS_BY_NAME: Mapping[str, GoalStatus] = types.MappingProxyType(
    {
        "abandoned": GoalStatus.ABANDONED,
        "blocked": GoalStatus.BLOCKED,
    },
)


def _draft_skip_reason(draft: GoalDraft, npcs: dict[UUID, NPCCard]) -> str | None:
    """Return a one-line reason if ``draft`` must be skipped, else ``None``.

    Three skip causes: unknown ``npc_uuid``, unknown ``target_uuid``,
    or the named NPC already carries an ACTIVE life goal. Combining
    them into one validator keeps :func:`apply_goal_drafts` linear.
    """
    npc = npcs.get(draft.npc_uuid)
    if npc is None:
        return "unknown npc_uuid '{0}'".format(draft.npc_uuid)
    if draft.target_uuid is not None and draft.target_uuid not in npcs:
        return "unknown target_uuid '{0}' for npc '{1}'".format(draft.target_uuid, draft.npc_uuid)
    if npc.life_goal is not None and npc.life_goal.status is GoalStatus.ACTIVE:
        return "npc '{0}' already carries ACTIVE life_goal".format(draft.npc_uuid)
    return None


def apply_goal_drafts(npcs: dict[UUID, NPCCard], drafts: list[GoalDraft]) -> None:
    """Stamp each valid :class:`GoalDraft` onto its named NPC's life slot.

    Validation lives in :func:`_draft_skip_reason`; on any reason the
    draft is logged and dropped. Refuses to overwrite an NPC's ACTIVE
    life goal so a Chronicler hallucination cannot derail a vendetta
    in flight.
    """
    for draft in drafts:
        skip_reason = _draft_skip_reason(draft, npcs)
        if skip_reason is not None:
            logger.warning("Chronicler GoalDraft skipped: {0}", skip_reason)
            continue
        npcs[draft.npc_uuid].life_goal = Goal(
            scope=GoalScope.LIFE,
            kind=draft.kind,
            description=draft.description,
            target_uuid=draft.target_uuid,
        )


def _apply_one_update(npcs: dict[UUID, NPCCard], update: GoalUpdate) -> None:
    """Flip one NPC's life-goal status if the NPC and an ACTIVE goal both exist."""
    npc = npcs.get(update.npc_uuid)
    if npc is None:
        logger.warning("Chronicler GoalUpdate references unknown npc_uuid '{0}'; skipping", update.npc_uuid)
        return
    goal = npc.life_goal
    if goal is None or goal.status is not GoalStatus.ACTIVE:
        return
    goal.status = _STATUS_BY_NAME[update.status]
    if update.reason:
        goal.record_progress("chronicler {0}: {1}".format(update.status, update.reason))


def apply_goal_updates(npcs: dict[UUID, NPCCard], updates: list[GoalUpdate]) -> None:
    """Apply each :class:`GoalUpdate` via :func:`_apply_one_update`."""
    for update in updates:
        _apply_one_update(npcs, update)
