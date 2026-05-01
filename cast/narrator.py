"""Narrator — converts raw scene/action data into literary text."""

from __future__ import annotations

from typing import Any

from loguru import logger

from cast.base_performer_class import BasePerformer
from cast.player_context import format_player_appearance, format_player_inventory
from cast.narrator_dedup import dedup_dialogue, dedup_npc_turns
from cast.narrator_labels import NarratorLabels, get_narrator_labels
from cast.narrator_wait import append_wait_parts, format_wait_context_bullets
from cast.schemas.turn_outputs import TurnOutputs
from cast.visible_entities import collect_for_turn
from models.scene import Scene
from prompts.narrator_prompts import get_narrator_prompts

_HISTORY_PREVIEW_CHARS = 200
_NARRATION_MAX_TOKENS = 450
_KEY_COMPLETED_EVENTS = "completed_events"
_KEY_WAIT_CONTEXT_LINES = "wait_context_lines"
_KEY_HOURS_WAITED = "hours_waited"
_KEY_TURN_INTENT = "turn_intent"


def _format_alias_list(names: list[str]) -> str:
    """Render an alias list as ``primary (aka: alias1, alias2)``.

    Single-element lists render just the primary so the Narrator does
    not see a noisy ``(aka: …)`` suffix when there is no real synonym
    to alternate with.
    """
    primary = names[0]
    aliases = names[1:]
    if not aliases:
        return primary
    return "{0} (aka: {1})".format(primary, ", ".join(aliases))


def _format_npc_label(snpc: Any, game_state: Any) -> str:
    """Format NPC label, gating names on ``player.known_npcs``.

    Routes through :meth:`NPCCard.known_names_for_player` — that's the
    single source of truth for the alias shape (introduced vs.
    descriptor vs. role fallback). A ``uuid`` set on the ``SceneNPC``
    that is missing from ``game_state.npcs`` is a broken invariant the
    NPC Ticker is supposed to prevent — surfaced as a warning so
    operators can trace the divergence while the player-facing
    fallback keeps rendering.
    """
    if snpc.uuid:
        npc = game_state.npcs.get(snpc.uuid)
        if npc is not None:
            return _format_alias_list(npc.known_names_for_player(game_state, snpc.role))
        logger.warning(
            "Narrator._format_npc_label: scene uuid={0} role={1} missing from game_state.npcs",
            snpc.uuid,
            snpc.role,
        )
    return snpc.role


def _resolve_current_location_id(game_state: Any) -> str | None:
    """Return the active location_id via player, then current scene."""
    player = getattr(game_state, "player", None)
    if player and player.location_id:
        return player.location_id
    scene = getattr(game_state, "current_scene", None)
    return getattr(scene, "location_id", None) if scene else None


def _resolve_current_location(game_state: Any) -> Any:
    """Return the player's current ``Location`` or ``None``.

    Logs a warning when the resolved ``location_id`` is not registered
    in ``game_state.locations`` — that state shouldn't happen in
    production and silently deactivates the Narrator's prior-damage
    surfacing when it does.
    """
    location_id = _resolve_current_location_id(game_state)
    if not location_id:
        return None
    location = game_state.locations.get(location_id)
    if location is None:
        logger.warning(
            "Narrator._resolve_current_location: location_id={0} not in game_state.locations",
            location_id,
        )
    return location


def _append_prior_damage_parts(raw_parts: list[str], game_state: Any, labels: NarratorLabels) -> None:
    """Append a localised ``Prior damage:`` line for every tracked object state.

    No-op when the player's current location is unresolvable or has
    no tracked object state.
    """
    location = _resolve_current_location(game_state)
    if location is None or not location.object_states:
        return
    damage_lines = [
        "- {0}: {1}".format(object_key, state) for object_key, state in sorted(location.object_states.items())
    ]
    raw_parts.append(labels.prior_damage.format("\n".join(damage_lines)))


def _build_narrator_context_kwargs(game_state: Any, language: str, is_new_scene: bool) -> dict[str, str]:
    """Build kwargs for ``Narrator.set_context``.

    ``world_mood`` renders only when both conditions hold: the
    World Chronicler has set a non-empty mood AND this turn is a
    scene entry. On CONTINUATION turns a standing order to weave
    mood into every response turns small actions into atmospheric
    embroidery, so we omit it there.
    """
    player = game_state.player
    ctx_kwargs: dict[str, str] = {
        "setting_name": game_state.setting.name,
        "time_period": game_state.setting.time_period,
        "time_of_day": game_state.game_time,
        "language": language,
        "player_appearance": format_player_appearance(player),
        "player_inventory": format_player_inventory(player),
    }
    mood = game_state.world_state.world_mood
    if mood and is_new_scene:
        ctx_kwargs["world_mood"] = mood
    return ctx_kwargs


class Narrator(BasePerformer):
    """Transforms raw agent outputs into vivid, literary narration.

    Resolves the per-locale system prompt, task prompt, and connector
    labels at construction time based on *language*. Unsupported
    languages transparently fall back to the English catalogs — see
    :func:`prompts.locales.resolve_locale`.
    """

    def __init__(self, *, llm_client: Any, language: str = "English"):
        prompts = get_narrator_prompts(language)
        super().__init__(
            llm_client=llm_client,
            system_prompt_template=prompts.system,
        )
        self._language = language
        self._narrate_template = prompts.narrate
        self._labels = get_narrator_labels(language)

    async def act(self, input_data: TurnOutputs, context: dict) -> str:
        """Transform raw turn outputs into literary narration.

        ``input_data``: A :class:`TurnOutputs` instance produced by
        :class:`cast.director_execution.PlanExecutor`.

        ``context``: Must contain ``player_action`` and ``game_state``.

        Returns a single narrated text string.
        """
        game_state = context["game_state"]
        is_new_scene = input_data.scene is not None

        # Best-effort: a bad scene/NPC invariant must not abort the turn.
        try:
            game_state.last_visible_entities = collect_for_turn(input_data, game_state)
        except Exception:
            logger.exception(
                "Narrator.act: collect_for_turn failed; proceeding without visible_entities (turn={0})",
                getattr(game_state, "turn_count", "?"),
            )
            game_state.last_visible_entities = []

        self.set_context(**_build_narrator_context_kwargs(game_state, self._language, is_new_scene))

        raw_parts = self._build_raw_parts(input_data, game_state, context.get("scene_history", []), is_new_scene)

        narrated = await self._send(
            self._narrate_template.render(
                **self._build_narration_kwargs(
                    context.get("player_action", ""),
                    "\n".join(raw_parts) if raw_parts else self._labels.no_scene_data,
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

        if input_data.scene is None:
            # CONTINUATION turns have no SceneBuilder-merged points_of_interest,
            # so surface tracked object state directly via the typed channel.
            _append_prior_damage_parts(raw_parts, game_state, self._labels)
        else:
            self._append_scene_parts(raw_parts, input_data.scene, game_state)

        self._append_turn_lines(raw_parts, input_data)
        return raw_parts

    def _append_turn_lines(self, raw_parts: list[str], input_data: TurnOutputs) -> None:
        """Append dialogue, new NPCs, items, wait, NPC turns and departures.

        Dialogue and ``npc_turns`` are deduplicated per-NPC before
        rendering so the Narrator does not serialise two entries for
        the same character into an ``and then… and then…`` cadence.
        """
        labels = self._labels
        for entry in dedup_dialogue(input_data.dialogue):
            raw_parts.append(labels.says.format(entry.npc_name, entry.response))
        raw_parts.extend(labels.new_person.format(desc) for desc in input_data.new_npcs)
        raw_parts.extend(labels.item_examined.format(desc) for desc in input_data.item_examination)
        raw_parts.extend(labels.object_interaction.format(desc) for desc in input_data.object_interactions)

        if input_data.wait:
            append_wait_parts(raw_parts, input_data, labels)

        for npc_turn in dedup_npc_turns(input_data.npc_turns):
            raw_parts.append(labels.meanwhile.format(npc_turn.npc_name, npc_turn.action))
        raw_parts.extend(labels.someone_departs.format(line) for line in input_data.npc_departures)

    def _append_history_parts(self, raw_parts: list[str], scene_history: list[dict]) -> None:
        """Append scene history summary to raw_parts."""
        lines = [
            self._labels.scene_history_player_line.format(
                entry["player_action"],
                entry.get("response_summary", "")[:_HISTORY_PREVIEW_CHARS],
            )
            for entry in scene_history
        ]
        raw_parts.append(self._labels.scene_history_heading.format("\n".join(lines)))

    def _append_scene_parts(self, raw_parts: list[str], scene: Scene, game_state: Any) -> None:
        """Append scene description parts to raw_parts."""
        labels = self._labels
        raw_parts.append(labels.scene.format(scene.description))
        if scene.ambient_description:
            raw_parts.append(labels.atmosphere.format(scene.ambient_description))
        if scene.npcs_present:
            npc_descriptions = [_format_npc_label(snpc, game_state) for snpc in scene.npcs_present]
            raw_parts.append(labels.people_visible.format(", ".join(npc_descriptions)))
        if scene.points_of_interest:
            poi_labels = [_format_alias_list(poi.names) for poi in scene.points_of_interest]
            raw_parts.append(labels.notable_things.format(", ".join(poi_labels)))

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
        if input_data.wait_context is not None:
            bullets = format_wait_context_bullets(input_data.wait_context, self._labels)
            if bullets:
                kwargs[_KEY_WAIT_CONTEXT_LINES] = "\n".join(bullets)
                kwargs[_KEY_HOURS_WAITED] = "{0:.1f}".format(input_data.wait_context.hours_waited)
        if input_data.intent:
            kwargs[_KEY_TURN_INTENT] = input_data.intent
        return kwargs
