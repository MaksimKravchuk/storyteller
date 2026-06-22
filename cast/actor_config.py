"""Module-level Actor helpers.

* ``format_past_memories`` — prompt-safe memory renderer.
* ``goal_prompt_vars`` — gated render of the standing-goal prompt section.

Extracted from ``cast.actor`` so those concerns don't contribute to that
module's import or member count.
"""

from __future__ import annotations

from cast._npc_active_goal import select_active_goal
from knowledge.node import KnowledgeNode
from models.goal import Goal, GoalKind
from models.npc_card import NPCCard
from prompts.actor_prompts import get_actor_prompts

_MEMORY_TEXT_MAX_CHARS = 200

_GOAL_NO_LAST_ACTION = "(none yet)"
_GOAL_NO_PROGRESS = "  (no notes yet — this is your first turn pursuing this goal)"
_GOAL_UNKNOWN_TARGET = "(unspecified)"

# Kinds whose standing-goal coaching is the combat STEALTH→ATTACK
# escalation. Every other kind gets the social (non-violent) coaching,
# except AVOID which gets the disengage coaching — see _goal_coaching.
_HOSTILE_GOAL_KINDS: frozenset[GoalKind] = frozenset(
    (
        GoalKind.KILL,
        GoalKind.PURSUE,
        GoalKind.DEFEND,
        GoalKind.FLEE,
        GoalKind.FLEE_SCENE,
    ),
)


def format_past_memories(memories: list[KnowledgeNode]) -> str:
    """Render a newline-joined bullet list of memory texts, truncated for prompt safety."""
    lines: list[str] = []
    for memory in memories:
        text = memory.text
        if len(text) > _MEMORY_TEXT_MAX_CHARS:
            text = "{0}...".format(text[: _MEMORY_TEXT_MAX_CHARS - 3])
        lines.append("- {0}".format(text))
    return "\n".join(lines)


def _format_goal_progress(notes: list[str]) -> str:
    if not notes:
        return _GOAL_NO_PROGRESS
    return "\n".join("  - {0}".format(note) for note in notes)


def _goal_coaching(kind: GoalKind, language: str) -> str:
    """Return the locale's coaching text for *kind*'s behavioural category.

    Combat kinds get the STEALTH→ATTACK escalation; AVOID gets the
    disengage coaching; every other kind gets the non-violent social
    coaching. Every :class:`GoalKind` maps to exactly one non-empty bank.
    """
    prompts = get_actor_prompts(language)
    if kind in _HOSTILE_GOAL_KINDS:
        return prompts.goal_coaching_hostile
    if kind is GoalKind.AVOID:
        return prompts.goal_coaching_avoid
    return prompts.goal_coaching_social


def _goal_section_vars(goal: Goal, target_name: str | None, language: str) -> dict[str, str]:
    return {
        "goal_kind": goal.kind.value,
        "goal_target": target_name or _GOAL_UNKNOWN_TARGET,
        "goal_turns_pursued": str(goal.turns_pursued),
        "goal_description": goal.description,
        "goal_last_action": goal.last_attempted_action or _GOAL_NO_LAST_ACTION,
        "goal_progress_notes": _format_goal_progress(goal.progress_notes),
        "goal_coaching": _goal_coaching(goal.kind, language),
    }


def goal_prompt_vars(
    npc: NPCCard,
    target_name: str | None,
    language: str,
) -> dict[str, str] | None:
    """Return Actor-prompt vars for the NPC's active goal, or ``None``.

    Tactical goal preferred over life — see :func:`select_active_goal`.
    Returns ``None`` when neither tier has an ACTIVE goal so the
    optional goal PromptSection is omitted from the rendered system
    prompt. ``language`` selects the locale's goal-coaching bank.
    """
    goal = select_active_goal(npc)
    if goal is None:
        return None
    return _goal_section_vars(goal, target_name, language)
