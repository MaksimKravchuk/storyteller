"""Prompt template for the AnachronismClassifier.

Renders the worldview the in-period NPCs hold, the player's stated
era, and the player's current action, and asks for a single JSON
verdict. The seed concept list is interpolated so the LLM has a
canonical vocabulary to reuse before it invents new slugs (concept
identifier stability is what lets the familiarity-discount loop in
:mod:`cast.anachronism` close — see issue #186 design notes).
"""

from __future__ import annotations

from prompts.base_template import PromptSection, PromptTemplate

ANACHRONISM_CLASSIFIER_SYSTEM = PromptTemplate(
    [
        PromptSection(
            name="role",
            template=(
                "You judge whether a player's action would seem out of period to "
                "an inhabitant of the in-game setting.\n"
                "Setting: {setting_name} ({time_period}).\n"
                "Region / social structure: {social_structure}.\n"
                "Period-appropriate technologies on hand: {technologies}.\n"
                "The player has self-declared they come from: {origin_era}.\n\n"
                "An action is anachronistic when its mechanism has no in-period "
                "explanation an ordinary witness could reach. A modern flashlight "
                "in a Roman forum is anachronistic; lighting a torch is not. A "
                "matter-of-fact claim about computers is anachronistic; a vague "
                "boast about strange foreign learning may not be."
            ),
            required_vars=[
                "setting_name",
                "time_period",
                "social_structure",
                "technologies",
                "origin_era",
            ],
        ),
        PromptSection(
            name="output_contract",
            template=(
                "Return JSON with exactly three fields:\n"
                "- strangeness_score (integer, 0-10): 0 = ordinary, "
                "5 = puzzling, 10 = world-shaking and inexplicable.\n"
                "- unfamiliar_concepts (list of snake_case strings): the "
                "abstract concepts an in-period witness would tag the "
                "experience with. Reuse the canonical seed concepts below "
                "verbatim when one fits; only invent a new slug when none "
                "does. The same gadget seen twice should produce the same "
                "slug both times.\n"
                "- perceived_rewrite (string): one short sentence describing "
                "the action as the in-period NPC would understand it — "
                'e.g. "the stranger held up a small mirror that lit by itself, '
                'as if a captured spark of lightning lived inside". Empty '
                "string when strangeness_score is 0."
            ),
            required_vars=[],
        ),
        PromptSection(
            name="seed_concepts",
            template=("Canonical seed concepts (reuse verbatim when applicable):\n{seed_concepts}"),
            required_vars=["seed_concepts"],
        ),
    ],
)


ANACHRONISM_CLASSIFIER_TASK = PromptTemplate(
    [
        PromptSection(
            name="task",
            template=(
                'Player action: "{player_action}"\n'
                "Player’s carried items: {player_inventory}\n\n"
                "Classify this action against the setting using the contract "
                "in the system prompt. Return JSON only."
            ),
            required_vars=["player_action", "player_inventory"],
        ),
    ],
)
