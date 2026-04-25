"""Module-level Actor helpers.

* ``ENVELOPE_MODE_DEFAULT`` — the ``ACTOR_ENVELOPE_MODE`` prod rollback
  lever, evaluated once at module import.
* ``format_past_memories`` — prompt-safe memory renderer.
* ``goal_prompt_vars`` — gated render of the standing-goal prompt section.

Extracted from ``cast.actor`` so those concerns don't contribute to that
module's import or member count.
"""

from __future__ import annotations

import os

from knowledge.node import KnowledgeNode
from loguru import logger
from models.goal import Goal, GoalStatus
from models.npc_card import NPCCard

_MEMORY_TEXT_MAX_CHARS = 200
_FALSY_ENV_VALUES = frozenset(("false", "0", "no", "off"))

_GOAL_NO_LAST_ACTION = "(none yet)"
_GOAL_NO_PROGRESS = "  (no notes yet — this is your first turn pursuing this goal)"
_GOAL_UNKNOWN_TARGET = "(unspecified)"


def _read_envelope_mode_env() -> bool:
    """Parse ACTOR_ENVELOPE_MODE with pydantic-style falsy tolerance.

    Treats the documented production-rollback values ("false", "0", "no",
    "off" — case-insensitive) as disabling envelope mode. Any other value
    (including typos) keeps the default envelope path on.
    """
    return os.environ.get("ACTOR_ENVELOPE_MODE", "true").strip().lower() not in _FALSY_ENV_VALUES


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

    Returns ``None`` when the NPC has no goal or its goal isn't active —
    callers skip ``set_context`` in that case so the optional goal
    PromptSection is omitted from the rendered system prompt.
    """
    goal = npc.current_goal
    if goal is None or goal.status is not GoalStatus.ACTIVE:
        return None
    return _goal_section_vars(goal, target_name)


# Prod rollback lever: set ACTOR_ENVELOPE_MODE=false/0/no/off in the deploy
# env to fall back to the legacy trailing-tag parser without a code
# redeploy. Evaluated once at module import — flipping the env var requires
# a process restart. Tests override via the ``envelope_mode`` constructor arg
# on ``cast.actor.Actor``.
ENVELOPE_MODE_DEFAULT: bool = _read_envelope_mode_env()
logger.info(
    "Actor envelope mode: {} (set ACTOR_ENVELOPE_MODE=false to roll back)",
    "ON" if ENVELOPE_MODE_DEFAULT else "OFF (legacy tag parser)",
)
