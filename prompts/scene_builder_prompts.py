"""Prompt templates for the Scene Builder agent."""

from prompts.base_template import PromptSection, PromptTemplate

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
                '  "points_of_interest": ["ONLY objects, environmental features, and locations the player'
                " can interact with — doors, signs, items, architecture. NEVER put people here; people go"
                ' in npcs_present"],\n'
                '  "ambient_description": "Sounds, smells, atmosphere",\n'
                '  "time_of_day": "{time_of_day}"\n'
                "}}"
            ),
            required_vars=["player_action", "time_of_day"],
        ),
    ]
)
