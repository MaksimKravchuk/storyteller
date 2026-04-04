"""Context formatting helpers for Director."""

from __future__ import annotations

from typing import Any

from models.game_state import GameState

_SCENE_SUMMARY_CHARS = 500

_KEY_PLAYER_ACTION = "player_action"
_KEY_ACTION_TYPE = "action_type"


def _format_scene_entry(entry: dict) -> str:
    """Format a single scene log entry as a bullet point."""
    action = entry[_KEY_PLAYER_ACTION]
    action_type = entry.get(_KEY_ACTION_TYPE, "?")
    return f"- Player: {action} -> {action_type}"


def _npc_label(npc: Any) -> str:
    """Format an NPC's name, appending physical status when not healthy."""
    if npc.physical_status and npc.physical_status != "healthy":
        return "{0} ({1})".format(npc.name, npc.physical_status)
    return npc.name


def format_npcs_present(scene: Any, game_state: GameState) -> str:
    """Format NPC names for the system prompt."""
    if not scene:
        return "None"
    all_npcs = game_state.npcs
    present = [snpc for snpc in scene.npcs_present if snpc.uuid and snpc.uuid in all_npcs]
    names = [_npc_label(all_npcs[snpc.uuid]) for snpc in present]
    return ", ".join(names) or "None"


def format_pois(scene: Any) -> str:
    """Format points of interest for the system prompt."""
    if scene and scene.points_of_interest:
        return ", ".join(scene.points_of_interest)
    return "None"


def format_scene_history(game_state: GameState) -> str | None:
    """Format recent scene actions for the system prompt."""
    scene_log = game_state.scene_conversation_log
    if not scene_log:
        return None
    recent = scene_log[-5:]
    lines = [_format_scene_entry(entry) for entry in recent]
    return "\n".join(lines)


def get_location_name(location_id: str | None, game_state: GameState) -> str:
    """Resolve a location ID to its name."""
    locations = game_state.locations
    if location_id and location_id in locations:
        return locations[location_id].name
    return "this place"


class ContextFormatter:
    """Manages Director system prompt context and turn logs."""

    def __init__(self, game_state: GameState) -> None:
        self._gs = game_state

    def sync_context(self, performer: Any) -> None:
        """Update system prompt variables from the current game state."""
        scene = self._gs.current_scene
        context_vars = dict(
            setting_name=self._gs.setting.name,
            time_period=self._gs.setting.time_period,
            scene_description=(scene.description if scene else "No scene set yet"),
            npcs_present=format_npcs_present(scene, self._gs),
            points_of_interest=format_pois(scene),
            game_time=self._gs.game_time,
            game_clock=str(round(self._gs.game_clock, 1)),
        )
        history_summary = format_scene_history(self._gs)
        if history_summary:
            context_vars["scene_history_summary"] = history_summary
        performer.set_context(**context_vars)

    def append_turn_logs(self, player_action: str, narrated_response: str, action_type: str) -> None:
        """Update game state conversation logs after a turn."""
        from cast.director import TURN_COUNTING_ACTIONS

        if action_type in TURN_COUNTING_ACTIONS:
            self._gs.turn_count += 1
        self._gs.conversation_log.append(
            {
                "turn": self._gs.turn_count,
                "scene_number": self._gs.scene_number,
                _KEY_PLAYER_ACTION: player_action,
                "response": narrated_response,
                "game_clock": self._gs.game_clock,
            }
        )
        self._gs.scene_conversation_log.append(
            {
                _KEY_PLAYER_ACTION: player_action,
                "response_summary": narrated_response[:_SCENE_SUMMARY_CHARS],
                _KEY_ACTION_TYPE: action_type,
            }
        )
