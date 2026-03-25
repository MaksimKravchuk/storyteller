"""Narrator — converts raw scene/action data into literary text."""

from __future__ import annotations

from typing import Any

from cast.base_performer_class import BasePerformer
from prompts.narrator_prompts import NARRATOR_NARRATE, NARRATOR_SYSTEM


class Narrator(BasePerformer):
    """Transforms raw agent outputs into vivid, literary narration."""

    def __init__(self, *, llm_client: Any, language: str = "English"):
        super().__init__(
            llm_client=llm_client,
            system_prompt_template=NARRATOR_SYSTEM,
        )
        self._language = language

    async def act(self, input_data: dict, context: dict) -> str:
        """Transform raw data into literary narration.

        ``input_data``: Dict with optional keys:
            - "scene": Scene description text
            - "dialogue": list of {"npc_name": str, "response": str}
            - "new_npcs": list of NPC descriptions
            - "completed_events": list of event descriptions

        ``context``: Must contain ``player_action`` and ``game_state``.

        Returns a single narrated text string.
        """
        from models.game_state import GameState

        game_state: GameState = context["game_state"]
        player_action: str = context.get("player_action", "")

        self.set_context(
            setting_name=game_state.setting.name,
            time_period=game_state.setting.time_period,
            time_of_day=game_state.game_time,
            language=self._language,
        )

        # Assemble raw material
        raw_parts: list[str] = []

        if "scene" in input_data:
            scene = input_data["scene"]
            if hasattr(scene, "description"):
                raw_parts.append(f"Scene: {scene.description}")
                if scene.ambient_description:
                    raw_parts.append(f"Atmosphere: {scene.ambient_description}")
                if scene.npcs_present:
                    raw_parts.append(f"People visible: {', '.join(scene.npcs_present)}")
                if scene.points_of_interest:
                    raw_parts.append(
                        f"Notable things: {', '.join(scene.points_of_interest)}"
                    )
            else:
                raw_parts.append(f"Scene: {scene}")

        if "dialogue" in input_data:
            for d in input_data["dialogue"]:
                raw_parts.append(f'{d["npc_name"]} says: {d["response"]}')

        if "new_npcs" in input_data:
            for npc_desc in input_data["new_npcs"]:
                raw_parts.append(f"New person appears: {npc_desc}")

        raw_material = "\n".join(raw_parts) if raw_parts else "No specific scene data."

        # Build the narration prompt
        kwargs: dict[str, str] = {
            "player_action": player_action,
            "raw_material": raw_material,
        }

        # Completed events (local ones the player can see)
        if "completed_events" in input_data and input_data["completed_events"]:
            kwargs["completed_events"] = "\n".join(
                f"- {ev}" for ev in input_data["completed_events"]
            )

        prompt = NARRATOR_NARRATE.render(**kwargs)
        narrated = await self._send(prompt, max_tokens=800)
        return narrated.strip()
