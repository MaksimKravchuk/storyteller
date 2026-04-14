"""Prompt-helper functions for the Narrative Test Agent.

These helpers flatten parts of a :class:`models.game_state.GameState`
snapshot into the strings the ``NARRATIVE_TEST_AUDIT`` prompt template
renders. They live outside ``cast.narrative_test_agent`` so that the
agent module itself stays focused on the :class:`NarrativeTestAgent`
class — WPS202 caps a single module at a handful of top-level members,
so we keep the public surface small and delegate fine-grained rendering
to two private helper modules.

The public API is:

- :func:`format_log` — simple bullet-list renderer for optional reviewer
  logs. Exposed directly because the helper is stateless and already
  tiny.
- :func:`build_audit_kwargs` — the single entry point the agent uses to
  assemble the keyword arguments for the audit prompt template.

Every other formatter is an implementation detail of those two.
"""

from __future__ import annotations

from cast._narrative_test_npc import format_npc_memory, format_npc_profiles
from cast._narrative_test_scene import (
    format_current_scene,
    format_recent_turns,
    format_world_threads,
)
from models.game_state import GameState

_EMPTY_PLACEHOLDER = "(none)"


def format_log(entries: list[str]) -> str:
    """Render an optional reviewer log (confrontation/autonomy) as bullets."""
    if not entries:
        return _EMPTY_PLACEHOLDER
    return "\n".join("- {0}".format(line) for line in entries)


def build_audit_kwargs(game_state: GameState, context: dict) -> dict[str, str]:
    """Assemble the keyword arguments for the ``NARRATIVE_TEST_AUDIT`` template."""
    return {
        "scene_number": str(game_state.scene_number),
        "turn_count": str(game_state.turn_count),
        "world_mood": game_state.world_state.world_mood or _EMPTY_PLACEHOLDER,
        "recent_turns": format_recent_turns(game_state.conversation_log),
        "current_scene": format_current_scene(game_state),
        "world_threads": format_world_threads(game_state.world_state.threads),
        "npc_profiles": format_npc_profiles(game_state),
        "npc_memory": format_npc_memory(game_state),
        "confrontation_log": format_log(context.get("confrontation_log") or []),
        "autonomy_log": format_log(context.get("autonomy_log") or []),
    }
