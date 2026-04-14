"""Scene Builder — generates scene descriptions from setting + player context."""

from __future__ import annotations

from typing import Any

from cast.base_performer_class import BasePerformer
from cast.schemas.scene_response import SceneResponse
from knowledge.scene_state import all_scene_deltas
from models.scene import Scene, SceneNPC
from prompts.scene_builder_prompts import SCENE_BUILDER_GENERATE, SCENE_BUILDER_SYSTEM

_SETTING_SUMMARY_MAX = 500


def _format_persistent_world_changes(deltas: dict[str, list[str]]) -> str:
    """Render the ``persistent_world_changes`` prompt section.

    The section is only rendered when at least one location has a
    delta recorded; empty input produces the empty string, which
    triggers the PromptTemplate's drop-empty-sections behaviour so
    the system prompt stays clean on the player's very first turn.
    """
    if not deltas:
        return ""
    lines = []
    for location_id in sorted(deltas):
        location_deltas = deltas[location_id]
        joined = " ".join(location_deltas)
        lines.append("- {0}: {1}".format(location_id, joined))
    return "\n".join(lines)


def _scene_from_response(scene_data: SceneResponse, fallback_time_of_day: str) -> Scene:
    """Convert a raw LLM ``SceneResponse`` payload into a typed ``Scene``."""
    npcs = [SceneNPC(role=role_str) for role_str in scene_data.npcs_present]
    return Scene(
        location_id=scene_data.location_id or "unknown",
        description=scene_data.description,
        npcs_present=npcs,
        points_of_interest=scene_data.points_of_interest,
        ambient_description=scene_data.ambient_description,
        time_of_day=scene_data.time_of_day or fallback_time_of_day,
    )


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
        self._prime_context(game_state)

        prompt = SCENE_BUILDER_GENERATE.render(
            player_action=input_data,
            time_of_day=game_state.game_time,
        )
        scene_data = await self._send_json(prompt, response_model=SceneResponse)
        return _scene_from_response(scene_data, game_state.game_time)

    def _prime_context(self, game_state: Any) -> None:
        """Prepare the system-prompt context for one scene build.

        Sets the always-present context variables (setting summary,
        current location, time of day) and additionally threads in the
        ``persistent_world_changes`` block when any scene-state deltas
        have been recorded. Split out of ``act`` to keep the main
        method within the WPS210 local-variable budget.
        """
        current_loc = game_state.current_scene.description if game_state.current_scene else "Starting area"
        self.set_context(
            setting_summary=game_state.setting.summary[:_SETTING_SUMMARY_MAX],
            current_location=current_loc,
            time_of_day=game_state.game_time,
        )
        deltas_block = _format_persistent_world_changes(all_scene_deltas(game_state.knowledge_graph))
        if deltas_block:
            self.set_context(persistent_world_changes=deltas_block)
