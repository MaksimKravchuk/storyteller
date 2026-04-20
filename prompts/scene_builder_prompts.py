"""Prompt templates for the Scene Builder agent.

This module owns the **English** Scene Builder catalog and the
locale-aware :func:`get_scene_builder_prompts` lookup. To add a new
locale, create a sibling ``scene_builder_prompts_<lang>.py`` module
and wire its bundle into :data:`_CATALOG` below.
"""

from __future__ import annotations

import types
from dataclasses import dataclass

from prompts.base_template import PromptSection, PromptTemplate
from prompts.locales import Locale, resolve_locale
from prompts.scene_builder_prompts_ru import SCENE_BUILDER_GENERATE_RU, SCENE_BUILDER_SYSTEM_RU

SCENE_BUILDER_SYSTEM = PromptTemplate(
    [
        PromptSection(
            name="role",
            template=(
                "You are a Scene Builder for an interactive text quest. "
                "You generate structured scene data — visual appearance, "
                "NPCs present, and points of interest. You do NOT write "
                "literary narration; the Narrator will do that from your data."
            ),
        ),
        PromptSection(
            name="setting",
            template=("Setting: {setting_summary}\nCurrent location: {current_location}\nTime of day: {time_of_day}"),
            required_vars=["setting_summary", "current_location", "time_of_day"],
        ),
        PromptSection(
            name="persistent_world_changes",
            template=(
                "Persistent world changes — these are durable deltas caused by the player "
                "in previous turns. If the scene you generate has a location_id matching one "
                "of the entries below, you MUST incorporate every listed change into the "
                "description and points_of_interest. Never regenerate an unchanged version.\n"
                "{persistent_world_changes}"
            ),
            required_vars=["persistent_world_changes"],
        ),
        PromptSection(
            name="known_object_states",
            template=(
                "Known object states — the objects listed below already have durable state "
                "from prior turns. You MUST preserve every listed state exactly; you may add "
                "new points of interest, but never reset a listed object to a pristine or "
                "undamaged version.\n"
                "{known_object_states}"
            ),
            required_vars=["known_object_states"],
        ),
        PromptSection(
            name="language",
            template=(
                "Fill every human-readable text field (description, npcs_present, "
                "points_of_interest, ambient_description) in {language}. Keep the JSON "
                "keys and the location_id / time_of_day values in English — they are "
                "machine-read."
            ),
            required_vars=["language"],
        ),
    ]
)


SCENE_BUILDER_GENERATE = PromptTemplate(
    [
        PromptSection(
            name="task",
            template=(
                'Player action: "{player_action}"\n\n'
                "Generate a scene. Output ONLY valid JSON:\n"
                "{{\n"
                '  "location_id": "a short snake_case id for this location",\n'
                '  "description": "Detailed visual description of the scene (what you see, architecture, objects)",\n'
                '  "npcs_present": ["EVERY person/character visible in the scene — guards, merchants,'
                ' beggars, passers-by, etc. Use role descriptions like: guard, merchant, beggar, scribe"],\n'
                '  "points_of_interest": ["3 to 5 items max. Pick ONLY the most story-bearing'
                " objects — things that carry information (boards, notices, signs, inscriptions),"
                " gate movement (doors, gates, stairs), hold contents (chests, barrels, crates),"
                " or have visible state the player might change (locks, torches, levers, fires)."
                " SKIP decorative or incidental architecture (niches, rings, mouldings, plinths,"
                " gutters) unless they carry a secret or a use. NEVER put people here; people go"
                ' in npcs_present"],\n'
                '  "ambient_description": "Sounds, smells, atmosphere",\n'
                '  "time_of_day": "{time_of_day}"\n'
                "}}"
            ),
            required_vars=["player_action", "time_of_day"],
        ),
    ]
)


@dataclass(frozen=True)
class SceneBuilderPrompts:
    """Per-locale Scene Builder prompt bundle."""

    system: PromptTemplate
    generate: PromptTemplate


_CATALOG: types.MappingProxyType[Locale, SceneBuilderPrompts] = types.MappingProxyType(
    {
        Locale.ENGLISH: SceneBuilderPrompts(system=SCENE_BUILDER_SYSTEM, generate=SCENE_BUILDER_GENERATE),
        Locale.RUSSIAN: SceneBuilderPrompts(system=SCENE_BUILDER_SYSTEM_RU, generate=SCENE_BUILDER_GENERATE_RU),
    }
)


def get_scene_builder_prompts(language: str | None) -> SceneBuilderPrompts:
    """Return the Scene Builder prompt bundle for *language*.

    Unrecognised languages transparently fall back to the English
    catalog (see :func:`prompts.locales.resolve_locale`). The returned
    bundle is a module-level singleton — callers must not mutate it.
    """
    return _CATALOG[resolve_locale(language)]
