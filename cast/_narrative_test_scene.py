"""Scene / turn / thread renderers for the Narrative Test Agent.

This is a private helper module for :mod:`cast.narrative_test_formatters`.
It groups the renderers that operate on the spatial and temporal parts
of a game snapshot — recent turns, the current scene, and world threads —
so that the parent module can stay under the WPS202 member cap.
"""

from __future__ import annotations

from typing import Any

from models.game_state import GameState
from models.world_state import WorldThread

_EMPTY_PLACEHOLDER = "(none)"
_MAX_TURNS_REVIEWED = 12
_NARRATED_PREVIEW_CHARS = 300


def _format_turn(idx: int, entry: dict) -> str:
    """Render a single conversation-log row as a numbered bullet."""
    player_action = entry.get("player_action", "")
    response_body = entry.get("response", "")[:_NARRATED_PREVIEW_CHARS]
    return "{0}. Player: {1}\n   Narrator: {2}".format(idx, player_action, response_body)


def format_recent_turns(conversation_log: list[dict]) -> str:
    """Render the most recent turns from ``GameState.conversation_log``."""
    if not conversation_log:
        return _EMPTY_PLACEHOLDER
    recent = conversation_log[-_MAX_TURNS_REVIEWED:]
    lines: list[str] = []
    for idx, entry in enumerate(recent, start=1):
        lines.append(_format_turn(idx, entry))
    return "\n".join(lines)


def _scene_body_lines(scene: Any) -> list[str]:
    """Render the optional scene-body lines (atmosphere, NPCs, POIs)."""
    lines: list[str] = []
    if scene.ambient_description:
        lines.append("Atmosphere: {0}".format(scene.ambient_description))
    if scene.npcs_present:
        npc_roles = ", ".join(snpc.role for snpc in scene.npcs_present)
        lines.append("Visible NPCs: {0}".format(npc_roles))
    if scene.points_of_interest:
        lines.append("Points of interest: {0}".format(", ".join(scene.points_of_interest)))
    return lines


def format_current_scene(game_state: GameState) -> str:
    """Render the current scene for the audit prompt."""
    scene = game_state.current_scene
    if scene is None:
        return _EMPTY_PLACEHOLDER
    header = [
        "Location: {0}".format(scene.location_id),
        "Description: {0}".format(scene.description),
    ]
    return "\n".join(header + _scene_body_lines(scene))


def format_world_threads(threads: list[WorldThread]) -> str:
    """Render every world thread (regardless of status) for the audit."""
    if not threads:
        return _EMPTY_PLACEHOLDER
    lines: list[str] = []
    for thread in threads:
        lines.append("- [{0}/{1}] {2}".format(thread.category, thread.status, thread.description))
    return "\n".join(lines)
