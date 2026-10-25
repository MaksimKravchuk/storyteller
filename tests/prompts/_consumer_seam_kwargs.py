"""Section-kwargs builders + LLM mock helpers for the consumer-seam contract tests.

Each builder mirrors one performer's ``set_context`` calls (including
optional sections) so the maximal-fixture game state populates every
``PromptSection`` of the corresponding template. The contract test
re-renders each section using the same kwargs and asserts the
rendered text appears in the prompt captured at the LLM seam.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

from cast import director_context, player_context, scene_place
from cast.actor_config import format_past_memories, goal_outcome_var, goal_prompt_vars
from cast.actor_memory import format_accessible_knowledge, select_actor_memories
from cast.hostility import format_hostile_actions_summary
from knowledge.query import KnowledgeQueryEngine
from knowledge.scene_state import all_scene_deltas
from models.game_state import GameState
from models.scene import Scene
from tests.prompts import _consumer_seam_state as state_mod

_TRUNCATE_SETTING_SUMMARY = 500
_TRUNCATE_SCENE_DESCRIPTION = 200
_TRUNCATE_SOCIAL_STRUCTURE = 300

NPC_RESPONSE_JSON = (
    '{"name": "Quintus", "biography": "A retired soldier.", '
    '"appearance": "weathered, broad-shouldered", '
    '"short_descriptor": "a weathered tavern keeper", '
    '"occupation": "tavern keeper", "personality_traits": ["gruff"], '
    '"speech_style": "clipped", "knowledge_scope": "local", '
    '"attributes": {"education": 3, "social_status": 3, "friendliness": 5, '
    '"suspicion": 5, "combat_skill": 3, "persuasion_skill": 3, '
    '"deception_skill": 3, "intimidation_skill": 3, "perception_skill": 3, '
    '"stealth_skill": 3}, "inventory": ["towel"], "goal": null}'
)
SCENE_RESPONSE_JSON = (
    '{"location_id": "forum", '
    '"description": "A wide forum, smoke in the air.", '
    '"npcs_present": ["guard"], '
    '"points_of_interest": [{"names": ["wooden notice board", "board"]}], '
    '"ambient_description": "The crackle of flames.", '
    '"time_of_day": "morning"}'
)
ACTOR_REPLY_JSON = '{"narration": "Halt.", "mood": null, "status": null, "revealed_names": []}'


def narrator_system_kwargs(game_state: GameState, language: str) -> dict[str, str]:
    """Mirror ``cast.narrator._build_narrator_context_kwargs`` (maximal)."""
    player = game_state.player
    return {
        "setting_name": game_state.setting.name,
        "time_period": game_state.setting.time_period,
        "time_of_day": game_state.game_time,
        "language": language,
        "player_appearance": player_context.format_player_appearance(player),
        "player_inventory": player_context.format_player_inventory(player),
        "world_mood": game_state.world_state.world_mood or "",
    }


def _actor_identity_kwargs(guard: Any, language: str) -> dict[str, str]:
    """Required-on-every-turn vars for the Actor dialogue prompt."""
    return {
        "npc_name": guard.name,
        "npc_occupation": guard.occupation,
        "location_name": state_mod.FORUM_LOCATION_NAME,
        "npc_biography": guard.biography,
        "personality_traits": ", ".join(guard.personality_traits),
        "speech_style": guard.speech_style,
        "npc_appearance": guard.appearance,
        "npc_inventory": ", ".join(guard.inventory),
        "current_mood": guard.current_mood,
        "physical_status": guard.physical_status,
        "language": language,
    }


def _actor_optional_kwargs(
    guard: Any,
    target: Any,
    game_state: GameState,
    knowledge_query: KnowledgeQueryEngine,
    language: str,
) -> dict[str, str]:
    """Vars for the optional Actor sections (knowledge, memory, hostility, goal)."""
    optional: dict[str, str] = {
        "accessible_knowledge": format_accessible_knowledge(knowledge_query, guard),
        "past_memories": format_past_memories(
            select_actor_memories(guard, knowledge_query, {"game_state": game_state}),
        ),
        "hostility_level": str(guard.hostility_level),
        "recent_hostile_actions_summary": format_hostile_actions_summary(guard.recent_hostile_actions),
    }
    goal_vars = goal_prompt_vars(guard, target.name, language)
    if goal_vars is not None:
        optional.update(goal_vars)
    outcome_text = goal_outcome_var(guard, language)
    if outcome_text is not None:
        optional["goal_last_outcome"] = outcome_text
    return optional


def actor_kwargs(game_state: GameState, language: str) -> dict[str, str]:
    """Mirror ``cast.actor.Actor.act`` + ``_apply_optional_sections`` (maximal)."""
    guard = game_state.npcs[state_mod.NPC_GUARD_ID]
    target = game_state.npcs[state_mod.NPC_TARGET_ID]
    knowledge_query = KnowledgeQueryEngine(game_state.knowledge_graph)
    return {
        **_actor_identity_kwargs(guard, language),
        **_actor_optional_kwargs(guard, target, game_state, knowledge_query, language),
    }


def _require_scene(game_state: GameState) -> Scene:
    """Narrow ``current_scene`` to non-None for the maximal-fixture call sites."""
    scene = game_state.current_scene
    assert scene is not None  # maximal fixture always sets current_scene
    return scene


def npc_generator_system_kwargs(game_state: GameState, language: str) -> dict[str, str]:
    """Mirror ``cast.npc_generator.NPCGenerator.act`` (maximal)."""
    scene = _require_scene(game_state)
    return {
        "setting_summary": game_state.setting.summary[:_TRUNCATE_SETTING_SUMMARY],
        "location_name": scene.description[:_TRUNCATE_SCENE_DESCRIPTION],
        "social_structure": game_state.setting.social_structure[:_TRUNCATE_SOCIAL_STRUCTURE],
        "language": language,
    }


def npc_generator_create_kwargs(_game_state: GameState, _language: str) -> dict[str, str]:
    return {
        "npc_request": "tavern keeper",
        "forbidden_names": "Aulus, Marcus Cinna",
        "candidate_targets": "Aulus, Marcus Cinna",
    }


def _sort_by_str_key(pair: Any) -> str:
    return str(pair[0])


def _scene_builder_optional_lines(game_state: GameState) -> tuple[str, str]:
    """Return (persistent_world_changes_lines, known_object_states_lines)."""
    location = game_state.locations[state_mod.LOCATION_ID]
    deltas = all_scene_deltas(game_state.knowledge_graph)
    delta_lines = "\n".join(
        "- {0}: {1}".format(scene_place.place_key(loc_id), " ".join(texts))
        for loc_id, texts in sorted(deltas.items(), key=_sort_by_str_key)
    )
    object_state_lines = "\n".join(
        "- {0}: {1}".format(obj_key, obj_state) for obj_key, obj_state in sorted(location.object_states.items())
    )
    return delta_lines, object_state_lines


def scene_builder_system_kwargs(game_state: GameState, language: str) -> dict[str, str]:
    """Mirror ``cast.scene_builder.SceneBuilder._prime_context`` (maximal)."""
    delta_lines, object_state_lines = _scene_builder_optional_lines(game_state)
    scene = _require_scene(game_state)
    return {
        "setting_summary": game_state.setting.summary[:_TRUNCATE_SETTING_SUMMARY],
        "current_location": scene.description,
        "time_of_day": game_state.game_time,
        "language": language,
        "persistent_world_changes": delta_lines,
        "known_object_states": object_state_lines,
        "known_places": scene_place.format_known_places(game_state),
    }


def director_system_kwargs(game_state: GameState, language: str) -> dict[str, str]:
    """Mirror ``cast.director_context.ContextFormatter.sync_context`` (maximal)."""
    scene = _require_scene(game_state)
    history = director_context.format_scene_history(game_state)
    assert history is not None  # maximal fixture must populate the log
    return {
        "setting_name": game_state.setting.name,
        "time_period": game_state.setting.time_period,
        "setting_technologies": ", ".join(game_state.setting.technologies)
        if game_state.setting.technologies
        else "unknown",
        "social_structure": game_state.setting.social_structure or "unknown",
        "scene_description": scene.description,
        "npcs_present": director_context.format_npcs_present(scene, game_state),
        "points_of_interest": director_context.format_pois(scene),
        "game_time": game_state.game_time,
        "game_clock": str(round(game_state.game_clock, 1)),
        "player_appearance": player_context.format_player_appearance(game_state.player),
        "player_inventory": player_context.format_player_inventory(game_state.player),
        "language": language,
        "scene_history_summary": history,
    }


def make_mock_llm(prose_body: str = "Narrated text.") -> AsyncMock:
    """Build an AsyncMock LLM client whose ``send_message`` returns a body."""
    client = AsyncMock()
    client.send_message = AsyncMock(
        return_value=AsyncMock(
            body=prose_body,
            model="test-model",
            usage={"prompt_tokens": 10, "completion_tokens": 5},
            tool_calls=[],
        ),
    )
    client.model = "test-model"
    return client


def _last_call_kwargs(client: AsyncMock) -> dict[str, Any]:
    return client.send_message.call_args.kwargs


def capture_system_prompt(client: AsyncMock) -> str:
    return _last_call_kwargs(client)["system_prompt"]


def capture_last_user_body(client: AsyncMock) -> str:
    messages = _last_call_kwargs(client)["messages"]
    return messages[-1].body
