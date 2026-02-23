"""Scene Builder — generates scene descriptions from setting + player context."""

from __future__ import annotations

from typing import Any

from cast.base_performer_class import BasePerformer
from models.scene import Scene
from prompts.scene_builder_prompts import SCENE_BUILDER_GENERATE, SCENE_BUILDER_SYSTEM


class SceneBuilder(BasePerformer):
    """Generates structured scene data for the Narrator to narrate."""

    def __init__(self, *, llm_client: Any):
        super().__init__(
            llm_client=llm_client,
            system_prompt_template=SCENE_BUILDER_SYSTEM,
        )

    async def act(self, input_data: str, context: dict) -> Scene:
        """Build a scene based on a player action and current game state.

        ``input_data``: The player's action string.
        ``context``: Must contain ``game_state``.

        Returns a ``Scene`` object.
        """
        from models.game_state import GameState

        game_state: GameState = context["game_state"]
        current_loc = (
            game_state.current_scene.description
            if game_state.current_scene
            else "Starting area"
        )

        self.set_context(
            setting_summary=game_state.setting.summary[:500],
            current_location=current_loc,
            time_of_day=game_state.game_time,
        )

        prompt = SCENE_BUILDER_GENERATE.render(
            player_action=input_data,
            time_of_day=game_state.game_time,
        )
        scene_data = await self._send_json(prompt)

        return Scene(
            location_id=scene_data.get("location_id", "unknown"),
            description=scene_data.get("description", ""),
            npcs_present=scene_data.get("npcs_present", []),
            points_of_interest=scene_data.get("points_of_interest", []),
            ambient_description=scene_data.get("ambient_description", ""),
            time_of_day=scene_data.get("time_of_day", game_state.game_time),
        )
