"""Prompt template for the anachronism classifier substrate."""

from __future__ import annotations

from prompts.base_template import PromptSection, PromptTemplate

ANACHRONISM_CLASSIFIER_SYSTEM = PromptTemplate(
    [
        PromptSection(
            name="worldview",
            template=(
                "WORLDVIEW\n"
                "The player character originates from {origin_era}. Judge what would feel unfamiliar, "
                "magical, impossible, taboo, or socially illegible to people in the current setting. "
                "Do not block the player action; classify only the perceived strangeness."
            ),
            required_vars=["origin_era"],
        ),
        PromptSection(
            name="setting",
            template=(
                "SETTING\n"
                "World: {setting_name}\n"
                "Time period: {time_period}\n"
                "Technologies: {setting_technologies}\n"
                "Social structure: {social_structure}"
            ),
            required_vars=["setting_name", "time_period", "setting_technologies", "social_structure"],
        ),
        PromptSection(
            name="action",
            template=(
                "ACTION\n"
                "Compare the player's action against the setting worldview. Then reuse these seed identifiers "
                "when applicable instead of inventing near-synonyms: {seed_concepts}. If no seed applies, "
                "add a concise snake_case identifier. Return score 0 and empty lists/text when the action "
                "contains no meaningful anachronism or unfamiliar concept."
            ),
            required_vars=["seed_concepts"],
        ),
    ]
)

ANACHRONISM_CLASSIFIER_REVIEW = (
    'Player action: "{player_action}"\n\n'
    "Classify only concepts that people in the setting would perceive as unfamiliar. Output ONLY valid JSON "
    "with this schema:\n"
    "{{\n"
    '  "strangeness_score": 0,\n'
    '  "unfamiliar_concepts": ["canonical_snake_case_identifier"],\n'
    '  "perceived_rewrite": "brief in-world description of the strange action"\n'
    "}}"
)
