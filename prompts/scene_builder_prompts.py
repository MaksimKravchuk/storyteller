"""Prompt templates for the Scene Builder agent.

This module owns the **English** Scene Builder catalog and the
locale-aware :func:`get_scene_builder_prompts` lookup. To add a new
locale, create a sibling ``scene_builder_prompts_<lang>.py`` module
and wire its bundle into the ``make_locale_lookup`` call below.
"""

from __future__ import annotations

from dataclasses import dataclass

from prompts.base_template import PromptSection, PromptTemplate
from prompts.locales import Locale, make_locale_lookup
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


SCENE_BUILDER_GENERATE = (
    'Player action: "{player_action}"\n\n'
    "Generate a scene. Output ONLY valid JSON:\n"
    "{{\n"
    '  "location_id": "a short snake_case id for this location",\n'
    '  "description": "Detailed visual description of the scene (what you see, architecture, objects)",\n'
    '  "npcs_present": ["EVERY person/character visible in the scene — guards, merchants,'
    " beggars, passers-by, etc. Use role descriptions like: guard, merchant, beggar, scribe."
    " When the player action asks for a social investigation opening, include at least one actionable contact,"
    ' such as a named vendor, clerk, guard, witness, informant, or an immediate path to one"],\n'
    '  "points_of_interest": [{{"names": ["full descriptive phrase",'
    ' "short head noun", "alt short head"]}}, ...],\n'
    '    // 3 to 7 items. Each entry is an object with a "names" list.\n'
    "    // names[0] is the primary descriptive phrase the Narrator can use in"
    " prose (e.g. 'a wooden notice board with wax-sealed scrolls'). names[1..]"
    " are 1-3 SHORT head-noun synonyms the Narrator is likely to use on"
    " second mention (e.g. 'notice board', 'board'). The short heads are what"
    " make inline highlighting robust — without them the post-match can't wrap"
    " abbreviated references. Include EVERY story-bearing object you expect the"
    " Narrator to describe prominently in prose: information carriers (boards,"
    " notices, signs, inscriptions, altars), movement gates (doors, gates,"
    " stairs, ladders), containers (chests, barrels, crates, strongboxes), and"
    " state-bearing fixtures (locks, torches, braziers, levers, fires). SKIP"
    " purely decorative architecture (plain niches, rings, mouldings, plinths,"
    " gutters) unless it hides a secret or has a use. NEVER put people here;"
    " people go in npcs_present.\n"
    '  "ambient_description": "Sounds, smells, atmosphere",\n'
    '  "time_of_day": "{time_of_day}"\n'
    "}}"
)


@dataclass(frozen=True)
class SceneBuilderPrompts:
    """Per-locale Scene Builder prompt bundle."""

    system: PromptTemplate
    generate: str


get_scene_builder_prompts = make_locale_lookup(
    {
        Locale.ENGLISH: SceneBuilderPrompts(system=SCENE_BUILDER_SYSTEM, generate=SCENE_BUILDER_GENERATE),
        Locale.RUSSIAN: SceneBuilderPrompts(system=SCENE_BUILDER_SYSTEM_RU, generate=SCENE_BUILDER_GENERATE_RU),
    }
)
