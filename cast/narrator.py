"""Narrator — converts raw scene/action data into literary text."""

from __future__ import annotations

from typing import Any

from cast.base_performer_class import BasePerformer
from cast.schemas.turn_outputs import TurnOutputs
from models.scene import Scene
from prompts.narrator_prompts import NARRATOR_NARRATE, NARRATOR_SYSTEM

_HISTORY_PREVIEW_CHARS = 200
_NARRATION_MAX_TOKENS = 800
_KEY_COMPLETED_EVENTS = "completed_events"


def _format_npc_label(snpc: Any, game_state: Any) -> str:
    """Format NPC label as 'Name (Occupation)' or fall back to role."""
    if snpc.uuid and snpc.uuid in game_state.npcs:
        npc = game_state.npcs[snpc.uuid]
        return "{0} ({1})".format(npc.name, npc.occupation)
    return snpc.role


class Narrator(BasePerformer):
    """Transforms raw agent outputs into vivid, literary narration."""

    def __init__(self, *, llm_client: Any, language: str = "English"):
        super().__init__(
            llm_client=llm_client,
            system_prompt_template=NARRATOR_SYSTEM,
        )
        self._language = language

    async def act(self, input_data: TurnOutputs, context: dict) -> str:
        """Transform raw turn outputs into literary narration.

        ``input_data``: A :class:`TurnOutputs` instance produced by
        :class:`cast.director_execution.PlanExecutor`.

        ``context``: Must contain ``player_action`` and ``game_state``.

        Returns a single narrated text string.
        """
        game_state = context["game_state"]
        is_new_scene = input_data.scene is not None

        self.set_context(
            setting_name=game_state.setting.name,
            time_period=game_state.setting.time_period,
            time_of_day=game_state.game_time,
            language=self._language,
        )

        raw_parts = self._build_raw_parts(input_data, game_state, context.get("scene_history", []), is_new_scene)

        narrated = await self._send(
            NARRATOR_NARRATE.render(
                **self._build_narration_kwargs(
                    context.get("player_action", ""),
                    "\n".join(raw_parts) if raw_parts else "No specific scene data.",
                    is_new_scene,
                    input_data,
                )
            ),
            max_tokens=_NARRATION_MAX_TOKENS,
        )
        return narrated.strip()

    def _build_raw_parts(
        self,
        input_data: TurnOutputs,
        game_state: Any,
        scene_history: list[dict],
        is_new_scene: bool,
    ) -> list[str]:
        """Assemble the raw material parts for narration."""
        raw_parts: list[str] = []

        if scene_history and not is_new_scene:
            self._append_history_parts(raw_parts, scene_history)

        if input_data.scene is not None:
            self._append_scene_parts(raw_parts, input_data.scene, game_state)

        for dialogue_entry in input_data.dialogue:
            raw_parts.append(f"{dialogue_entry.npc_name} says: {dialogue_entry.response}")

        for npc_desc in input_data.new_npcs:
            raw_parts.append(f"New person appears: {npc_desc}")

        for item_desc in input_data.item_examination:
            raw_parts.append(f"Item examined: {item_desc}")

        if input_data.wait:
            if (input_data.wait_reason or "") in ("", "voluntary"):
                raw_parts.append("The player waits and observes the surroundings.")
            else:
                raw_parts.append("The player cannot act — they are {0}.".format(input_data.wait_reason))

        for npc_turn in input_data.npc_turns:
            raw_parts.append("Meanwhile, {0}: {1}".format(npc_turn.npc_name, npc_turn.action))

        return raw_parts

    def _append_history_parts(self, raw_parts: list[str], scene_history: list[dict]) -> None:
        """Append scene history summary to raw_parts."""
        lines = [
            "- Player: {0} → {1}".format(
                entry["player_action"],
                entry.get("response_summary", "")[:_HISTORY_PREVIEW_CHARS],
            )
            for entry in scene_history
        ]
        raw_parts.append("What happened earlier in this scene:\n{0}".format("\n".join(lines)))

    def _append_scene_parts(self, raw_parts: list[str], scene: Scene, game_state: Any) -> None:
        """Append scene description parts to raw_parts."""
        raw_parts.append(f"Scene: {scene.description}")
        if scene.ambient_description:
            raw_parts.append(f"Atmosphere: {scene.ambient_description}")
        if scene.npcs_present:
            npc_descriptions = [_format_npc_label(snpc, game_state) for snpc in scene.npcs_present]
            raw_parts.append("People visible: {0}".format(", ".join(npc_descriptions)))
        if scene.points_of_interest:
            raw_parts.append("Notable things: {0}".format(", ".join(scene.points_of_interest)))

    def _build_narration_kwargs(
        self,
        player_action: str,
        raw_material: str,
        is_new_scene: bool,
        input_data: TurnOutputs,
    ) -> dict[str, str]:
        """Build keyword arguments for the narration prompt template."""
        kwargs: dict[str, str] = {
            "player_action": player_action,
            "raw_material": raw_material,
            "scene_type": "NEW_SCENE" if is_new_scene else "CONTINUATION",
        }
        if input_data.completed_events:
            kwargs[_KEY_COMPLETED_EVENTS] = "\n".join(f"- {ev}" for ev in input_data.completed_events)
        return kwargs
