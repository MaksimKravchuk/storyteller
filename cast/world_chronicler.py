"""World Chronicler — advances the living-world sandbox between scenes."""

from __future__ import annotations

from typing import Any

from cast.base_performer_class import BasePerformer
from cast.schemas.chronicler_response import ChroniclerResponse
from cast.schemas.turn_outputs import TurnOutputs
from models.game_state import GameState
from models.world_state import WorldThread
from prompts.chronicler_prompts import CHRONICLER_ADVANCE, CHRONICLER_SYSTEM

_EMPTY_THREADS_PLACEHOLDER = "(no open threads)"
_EMPTY_TURN_PLACEHOLDER = "(nothing notable happened)"
_UNKNOWN_LOCATION_LABEL = "unknown"
_TURN_SUMMARY_LIMIT = 600


def _describe_current_location(game_state: GameState) -> str:
    """Return a short description of the current scene, or a fallback label."""
    scene = game_state.current_scene
    if scene is None:
        return _UNKNOWN_LOCATION_LABEL
    return scene.description


def _format_threads(threads: list[WorldThread]) -> str:
    """Render open threads as numbered bullets for the prompt."""
    open_threads = [thread for thread in threads if thread.status == "open"]
    if not open_threads:
        return _EMPTY_THREADS_PLACEHOLDER
    lines = [
        "{0}. [{1}] {2} — uuid={3}".format(
            idx + 1,
            thread.category,
            thread.description,
            thread.uuid,
        )
        for idx, thread in enumerate(open_threads)
    ]
    return "\n".join(lines)


def _structural_turn_lines(turn: TurnOutputs) -> list[str]:
    """Scene / new-NPC / dialogue bullets — the 'what the player did' half."""
    lines: list[str] = []
    if turn.scene is not None:
        preview = turn.scene.description[:_TURN_SUMMARY_LIMIT]
        lines.append("Scene built: {0}".format(preview))
    if turn.new_npcs:
        lines.append("New NPCs: {0}".format(", ".join(turn.new_npcs)))
    for entry in turn.dialogue:
        lines.append("Dialogue — {0}: {1}".format(entry.npc_name, entry.response))
    return lines


def _background_turn_lines(turn: TurnOutputs) -> list[str]:
    """Items, NPC turns, departures, events, wait — the 'what else happened' half."""
    lines: list[str] = []
    for item_line in turn.item_examination:
        lines.append("Item examined: {0}".format(item_line))
    for npc_turn_entry in turn.npc_turns:
        lines.append("NPC {0}: {1}".format(npc_turn_entry.npc_name, npc_turn_entry.action))
    for departure_line in turn.npc_departures:
        lines.append("NPC departs: {0}".format(departure_line))
    for event_line in turn.completed_events:
        lines.append("Event resolved: {0}".format(event_line))
    if turn.wait:
        lines.append("Player waited ({0})".format(turn.wait_reason or "voluntary"))
    return lines


def _summarize_turn(turn: TurnOutputs) -> str:
    """Flatten the typed turn into a few-line text dump."""
    lines = _structural_turn_lines(turn) + _background_turn_lines(turn)
    return "\n".join(lines) if lines else _EMPTY_TURN_PLACEHOLDER


class WorldChronicler(BasePerformer):
    """Advances world threads, schedules offscreen events, and sets world_mood."""

    def __init__(self, *, llm_client: Any):
        super().__init__(
            llm_client=llm_client,
            system_prompt_template=CHRONICLER_SYSTEM,
        )

    async def act(self, input_data: TurnOutputs, context: dict) -> ChroniclerResponse:
        """Produce a conservative set of world updates for the current scene.

        ``input_data``: The :class:`TurnOutputs` assembled by the
        :class:`cast.director_execution.PlanExecutor` earlier this turn.

        ``context``: Must contain ``game_state``. ``player_action`` is
        optional and used only for logging.

        Returns a :class:`ChroniclerResponse`. Schema-validation or
        decode failures bubble up to the caller, which treats any
        exception as "chronicler stayed silent this turn".
        """
        game_state: GameState = context["game_state"]
        current_location = _describe_current_location(game_state)

        self.set_context(
            setting_name=game_state.setting.name,
            time_period=game_state.setting.time_period,
            current_location=current_location,
        )

        prompt = CHRONICLER_ADVANCE.render(
            scene_number=str(game_state.scene_number),
            open_threads=_format_threads(game_state.world_state.threads),
            turn_summary=_summarize_turn(input_data),
        )
        return await self._send_json(prompt, response_model=ChroniclerResponse)
