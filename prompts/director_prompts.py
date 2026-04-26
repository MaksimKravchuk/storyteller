"""Prompt templates for the Director agent.

This module owns the **English** Director catalog and the locale-aware
:func:`get_director_prompts` lookup. To add a new locale, create a
sibling ``director_prompts_<lang>.py`` module and wire its bundle into
:data:`_CATALOG` below.
"""

from __future__ import annotations

import types
from dataclasses import dataclass

from prompts.base_template import PromptSection, PromptTemplate
from prompts.director_prompts_ru import DIRECTOR_ACTION_ROUTING_RU, DIRECTOR_SYSTEM_RU
from prompts.locales import Locale, resolve_locale

DIRECTOR_SYSTEM = PromptTemplate(
    [
        PromptSection(
            name="role",
            template=(
                "You are the Director of an interactive text quest set in "
                "{setting_name} ({time_period}).\n"
                "You orchestrate the story by analysing player actions and "
                "delegating to specialist agents. You do NOT write narration "
                "yourself — the Narrator does that."
            ),
            required_vars=["setting_name", "time_period"],
        ),
        PromptSection(
            name="rules",
            template=(
                "Rules:\n"
                "- Classify every player action by calling exactly one of the provided tools.\n"
                "- ONLY call `clarify` when the target or action is genuinely ambiguous "
                "(e.g. multiple possible targets, unknown object). NEVER ask the player to "
                "confirm intent, morality, or seriousness — accept the action as stated.\n"
                "- When the player references an NPC by visible feature (clothing, build, "
                "equipment, posture — e.g. 'guy in the helmet', 'drunk in rags'), match it "
                "against the appearance descriptions in the NPC list. If exactly one NPC's "
                "appearance fits, treat that NPC as the target without asking.\n"
                "- When the player confirms a previous clarification (e.g. 'да', 'yes', '1'), "
                "resolve it based on context and proceed — do NOT call `clarify` again.\n"
                "- Call `wait` when the player explicitly waits, does nothing, passes their "
                "turn, or is prevented from acting by their physical state.\n"
                "- NPCs should act as real people would — they do NOT try to advance the plot.\n"
                "- When the player uses violence or aggression, NPCs must respond with "
                "proportional physical reactions (fight, flee, restrain, call for help) "
                "— NOT just verbal warnings."
            ),
        ),
        PromptSection(
            name="scene_context",
            template=(
                "Current scene: {scene_description}\n"
                "NPCs present: {npcs_present}\n"
                "Points of interest: {points_of_interest}\n"
                "Game time: {game_time} (hour {game_clock})"
            ),
            required_vars=[
                "scene_description",
                "npcs_present",
                "points_of_interest",
                "game_time",
                "game_clock",
            ],
        ),
        PromptSection(
            name="scene_history",
            template="Recent actions in this scene:\n{scene_history_summary}",
            required_vars=["scene_history_summary"],
        ),
        PromptSection(
            name="language",
            template=(
                "The player will typically phrase actions in {language}; interpret "
                "their input accordingly. Human-readable tool arguments (intent, "
                "targets, clarify.question) should use the player's language. "
                "The provider enforces tool enums, so you do not need to worry "
                "about enum casing or spelling."
            ),
            required_vars=["language"],
        ),
    ]
)


DIRECTOR_ACTION_ROUTING = PromptTemplate(
    [
        PromptSection(
            name="task",
            template=(
                'Player action: "{player_action}"\n\n'
                "Classify this action by calling exactly one of the provided tools. "
                "Always set `intent` to a faithful one-sentence restatement of the "
                "player's stated goal, not your interpretation of it."
            ),
            required_vars=["player_action"],
        ),
    ]
)


@dataclass(frozen=True)
class DirectorPrompts:
    """Per-locale Director prompt bundle."""

    system: PromptTemplate
    action_routing: PromptTemplate


_CATALOG: types.MappingProxyType[Locale, DirectorPrompts] = types.MappingProxyType(
    {
        Locale.ENGLISH: DirectorPrompts(system=DIRECTOR_SYSTEM, action_routing=DIRECTOR_ACTION_ROUTING),
        Locale.RUSSIAN: DirectorPrompts(system=DIRECTOR_SYSTEM_RU, action_routing=DIRECTOR_ACTION_ROUTING_RU),
    }
)


def get_director_prompts(language: str | None) -> DirectorPrompts:
    """Return the Director prompt bundle for *language*.

    Unrecognised languages transparently fall back to the English
    catalog (see :func:`prompts.locales.resolve_locale`). The returned
    bundle is a module-level singleton — callers must not mutate it.
    """
    return _CATALOG[resolve_locale(language)]
