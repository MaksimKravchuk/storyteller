"""Module-level Actor helpers.

* ``format_past_memories`` — prompt-safe memory renderer.
* ``goal_prompt_vars`` — gated render of the standing-goal prompt section.

Extracted from ``cast.actor`` so those concerns don't contribute to that
module's import or member count.
"""

from __future__ import annotations

from cast._npc_active_goal import select_active_goal
from knowledge.node import KnowledgeNode
from models.goal import Goal
from models.npc_card import NPCCard

_MEMORY_TEXT_MAX_CHARS = 200

_GOAL_NO_LAST_ACTION = "(none yet)"
_GOAL_NO_PROGRESS = "  (no notes yet — this is your first turn pursuing this goal)"
_GOAL_UNKNOWN_TARGET = "(unspecified)"


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


def _goal_section_vars(goal: Goal, target_name: str | None) -> dict[str, str]:
    return {
        "goal_kind": goal.kind.value,
        "goal_target": target_name or _GOAL_UNKNOWN_TARGET,
        "goal_turns_pursued": str(goal.turns_pursued),
        "goal_description": goal.description,
        "goal_last_action": goal.last_attempted_action or _GOAL_NO_LAST_ACTION,
        "goal_progress_notes": _format_goal_progress(goal.progress_notes),
    }


def goal_prompt_vars(npc: NPCCard, target_name: str | None) -> dict[str, str] | None:
    """Return Actor-prompt vars for the NPC's active goal, or ``None``.

    Tactical goal preferred over life — see :func:`select_active_goal`.
    Returns ``None`` when neither tier has an ACTIVE goal so the
    optional goal PromptSection is omitted from the rendered system
    prompt.
    """
    goal = select_active_goal(npc)
    if goal is None:
        return None
    return _goal_section_vars(goal, target_name)
