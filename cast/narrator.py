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
        scene_history: list[dict] = context.get("scene_history", [])
        is_new_scene: bool = "scene" in input_data

        self.set_context(
            setting_name=game_state.setting.name,
            time_period=game_state.setting.time_period,
            time_of_day=game_state.game_time,
            language=self._language,
        )

        # Assemble raw material
        raw_parts: list[str] = []

        # On CONTINUATION turns, inject recent scene history so the narrator
        # knows what happened before (e.g. an ongoing fight).
        if scene_history and not is_new_scene:
            history_lines = [
                f"- Player: {entry['player_action']} → {entry.get('response_summary', '')[:200]}"
                for entry in scene_history
            ]
            history = "\n".join(history_lines)
            raw_parts.append(f"What happened earlier in this scene:\n{history}")

        if is_new_scene:
            scene = input_data["scene"]
            if hasattr(scene, "description"):
                raw_parts.append(f"Scene: {scene.description}")
                if scene.ambient_description:
                    raw_parts.append(f"Atmosphere: {scene.ambient_description}")
                if scene.npcs_present:
                    npc_descriptions: list[str] = []
                    for snpc in scene.npcs_present:
                        if snpc.uuid and snpc.uuid in game_state.npcs:
                            npc = game_state.npcs[snpc.uuid]
                            npc_descriptions.append(f"{npc.name} ({npc.occupation})")
                        else:
                            npc_descriptions.append(snpc.role)
                    raw_parts.append(f"People visible: {', '.join(npc_descriptions)}")
                if scene.points_of_interest:
                    raw_parts.append(f"Notable things: {', '.join(scene.points_of_interest)}")
            else:
                raw_parts.append(f"Scene: {scene}")

        for dialogue_entry in input_data.get("dialogue", []):
            raw_parts.append(f"{dialogue_entry['npc_name']} says: {dialogue_entry['response']}")

        for npc_desc in input_data.get("new_npcs", []):
            raw_parts.append(f"New person appears: {npc_desc}")

        raw_material = "\n".join(raw_parts) if raw_parts else "No specific scene data."

        # Build the narration prompt
        scene_type = "NEW_SCENE" if is_new_scene else "CONTINUATION"
        kwargs: dict[str, str] = {
            "player_action": player_action,
            "raw_material": raw_material,
            "scene_type": scene_type,
        }

        # Completed events (local ones the player can see)
        if "completed_events" in input_data and input_data["completed_events"]:
            kwargs["completed_events"] = "\n".join(f"- {ev}" for ev in input_data["completed_events"])

        prompt = NARRATOR_NARRATE.render(**kwargs)
        narrated = await self._send(prompt, max_tokens=800)
        return narrated.strip()
