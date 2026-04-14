"""NPC roster and memory renderers for the Narrative Test Agent.

This is a private helper module for :mod:`cast.narrative_test_formatters`.
It groups the renderers that operate on the NPC portion of a game snapshot
so that the parent module can stay under the WPS202 member cap.
"""

from __future__ import annotations

from typing import Any

from models.game_state import GameState

_EMPTY_PLACEHOLDER = "(none)"
_MAX_NPC_MEMORY_LINES = 6
_MEMORY_EXCERPT_CHARS = 120


def _format_npc_profile(npc: Any) -> str:
    """Render a single NPC roster line."""
    traits = ", ".join(npc.personality_traits) if npc.personality_traits else "—"
    return "- {0} ({1}) | mood={2}, traits={3}".format(npc.name, npc.occupation, npc.current_mood, traits)


def format_npc_profiles(game_state: GameState) -> str:
    """Render the full NPC roster for the audit prompt."""
    if not game_state.npcs:
        return _EMPTY_PLACEHOLDER
    lines: list[str] = []
    for npc in game_state.npcs.values():
        lines.append(_format_npc_profile(npc))
    return "\n".join(lines)


def _memory_excerpt(entry: dict) -> str:
    """Extract a truncated ``content`` excerpt from one memory entry."""
    return entry.get("content", "")[:_MEMORY_EXCERPT_CHARS]


def _npc_memory_line(npc: Any) -> str | None:
    """Render one NPC's recent conversation history, or ``None`` if empty."""
    history = npc.conversation_history[-_MAX_NPC_MEMORY_LINES:]
    if not history:
        return None
    excerpts = "; ".join(_memory_excerpt(entry) for entry in history)
    return "{0}: {1}".format(npc.name, excerpts)


def format_npc_memory(game_state: GameState) -> str:
    """Render NPC memory excerpts for every NPC that has conversation history."""
    if not game_state.npcs:
        return _EMPTY_PLACEHOLDER
    lines: list[str] = []
    for npc in game_state.npcs.values():
        rendered = _npc_memory_line(npc)
        if rendered is not None:
            lines.append(rendered)
    return "\n".join(lines) if lines else _EMPTY_PLACEHOLDER
