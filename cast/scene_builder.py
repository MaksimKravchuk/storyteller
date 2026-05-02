"""Scene Builder — generates scene descriptions from setting + player context."""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID

from loguru import logger

from cast._scene_location import coerce_scene_location_id
from cast.base_performer_class import BasePerformer
from cast.schemas.scene_response import SceneResponse
from knowledge.scene_state import all_scene_deltas
from models.scene import PointOfInterest, Scene, SceneNPC, coerce_point_of_interest
from prompts.scene_builder_prompts import get_scene_builder_prompts

_SETTING_SUMMARY_MAX = 500


def _format_persistent_world_changes(deltas: dict[UUID, list[str]]) -> str:
    """Render the ``persistent_world_changes`` prompt section.

    The section is only rendered when at least one location has a
    delta recorded; empty input produces the empty string, which
    triggers the PromptTemplate's drop-empty-sections behaviour so
    the system prompt stays clean on the player's very first turn.
    """
    if not deltas:
        return ""
    lines = []
    # Sort by canonical string form so the rendered prompt stays
    # alphabetical (matching what a human reading the prompt sees) and
    # deterministic across runs — UUIDs are orderable by their 128-bit
    # int, but lexicographic order matches the rendered text.
    for location_id in sorted(deltas, key=str):
        location_deltas = deltas[location_id]
        joined = " ".join(location_deltas)
        lines.append("- {0}: {1}".format(location_id, joined))
    return "\n".join(lines)


def _format_known_object_states(object_states: dict[str, str]) -> str:
    """Render the ``known_object_states`` prompt section.

    Returns the empty string whenever the current location has no
    tracked object state, which triggers the PromptTemplate's
    drop-empty-sections behaviour so the system prompt stays clean.
    """
    if not object_states:
        return ""
    lines: list[str] = []
    for object_key in sorted(object_states):
        lines.append("- {0}: {1}".format(object_key, object_states[object_key]))
    return "\n".join(lines)


def _key_mentioned(object_key: str, scene: Scene) -> bool:
    """Return True when ``object_key`` already appears as a whole word in the scene.

    Uses a word-boundary regex so short keys like ``bar`` do not
    false-match inside ``barricade`` — the safety-net append must
    still fire when the LLM only *happens* to share a word fragment
    with the stored key.
    """
    pattern = re.compile(r"\b{0}\b".format(re.escape(object_key.lower())))
    if pattern.search(scene.description.lower()):
        return True
    poi_names = [name.lower() for poi in scene.points_of_interest for name in poi.names]
    return any(pattern.search(name) for name in poi_names)


def _merge_known_object_states(scene: Scene, object_states: dict[str, str]) -> None:
    """Append any tracked object state the LLM omitted from the scene.

    The system prompt instructs the LLM to preserve every listed state,
    but LLMs occasionally elide entries. This safety net walks the
    authoritative ``Location.object_states`` and, for any entry whose
    key is not already whole-word-mentioned in ``points_of_interest``
    or the scene description, appends a synthesized point of interest
    so the Narrator still surfaces the entry downstream. Detection is
    key-presence only: a description that mentions the key but
    paraphrases the state ("the shutter is freshly oiled") will not
    trigger the append. The real line of defence against silent
    resets is the ``known_object_states`` PromptSection instructing
    the LLM never to reset a listed state to pristine.
    """
    for object_key, state_description in object_states.items():
        if not _key_mentioned(object_key, scene):
            scene.points_of_interest.append(
                PointOfInterest(names=["{0} ({1})".format(object_key, state_description)]),
            )


def _current_object_states(game_state: Any) -> dict[str, str]:
    """Return the ``object_states`` dict for the player's current location.

    Resolves the location via the player's ``location_id``; falls back
    to the current scene's ``location_id`` when the player has not yet
    been placed. Returns an empty dict when no location is resolvable;
    a resolvable id that is not registered in ``game_state.locations``
    is logged as a warning because it deactivates KER-16 silently.
    """
    player = getattr(game_state, "player", None)
    location_id = player.location_id if player and player.location_id else None
    if not location_id:
        scene = getattr(game_state, "current_scene", None)
        location_id = getattr(scene, "location_id", None) if scene else None
    if not location_id:
        return {}
    location = game_state.locations.get(location_id)
    if location is None:
        logger.warning(
            "SceneBuilder._current_object_states: location_id={0} not in game_state.locations",
            location_id,
        )
        return {}
    return dict(location.object_states)


def _scene_from_response(scene_data: SceneResponse, fallback_time_of_day: str) -> Scene:
    """Convert a raw LLM ``SceneResponse`` payload into a typed ``Scene``."""
    npcs = [SceneNPC(role=role_str) for role_str in scene_data.npcs_present]
    pois = [
        coerce_point_of_interest(raw if isinstance(raw, str) else raw.model_dump())
        for raw in scene_data.points_of_interest
    ]
    location_id = coerce_scene_location_id(scene_data.location_id)
    return Scene(
        location_id=location_id,
        description=scene_data.description,
        npcs_present=npcs,
        points_of_interest=pois,
        ambient_description=scene_data.ambient_description,
        time_of_day=scene_data.time_of_day or fallback_time_of_day,
    )


class SceneBuilder(BasePerformer):
    """Generates structured scene data for the Narrator to narrate."""

    def __init__(self, *, llm_client: Any, language: str = "English"):
        prompts = get_scene_builder_prompts(language)
        super().__init__(
            llm_client=llm_client,
            system_prompt_template=prompts.system,
        )
        self._generate_template = prompts.generate
        self.set_context(language=language)

    async def act(self, input_data: str, context: dict) -> Scene:
        """Build a scene based on a player action and current game state.

        ``input_data``: The player's action string.
        ``context``: Must contain ``game_state``.

        Returns a ``Scene`` object.
        """
        from models.game_state import GameState

        game_state: GameState = context["game_state"]
        self._prime_context(game_state)

        prompt = self._generate_template.format(
            player_action=input_data,
            time_of_day=game_state.game_time,
        )
        scene_data = await self._send_json(prompt, response_model=SceneResponse)
        scene = _scene_from_response(scene_data, game_state.game_time)
        _merge_known_object_states(scene, _current_object_states(game_state))
        return scene

    def _prime_context(self, game_state: Any) -> None:
        """Prepare the system-prompt context for one scene build.

        Sets the always-present context variables (setting summary,
        current location, time of day) and additionally threads in the
        ``persistent_world_changes`` and ``known_object_states`` blocks
        when any deltas or tracked object states exist. Split out of
        ``act`` to keep the main method within the WPS210
        local-variable budget.
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
        object_states_block = _format_known_object_states(_current_object_states(game_state))
        if object_states_block:
            self.set_context(known_object_states=object_states_block)
