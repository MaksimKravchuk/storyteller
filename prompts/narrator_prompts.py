"""Prompt templates for the Narrator agent.

This module owns the **English** Narrator catalog and the
locale-aware :func:`get_narrator_prompts` lookup. To add a new
locale, create a sibling ``narrator_prompts_<lang>.py`` module and
wire its bundle into :data:`_CATALOG` below.
"""

from __future__ import annotations

import types
from dataclasses import dataclass

from prompts.base_template import PromptSection, PromptTemplate
from prompts.locales import Locale, resolve_locale
from prompts.narrator_prompts_ru import NARRATOR_NARRATE_RU, NARRATOR_SYSTEM_RU

NARRATOR_SYSTEM = PromptTemplate(
    [
        PromptSection(
            name="role",
            template=(
                "You are the Narrator of an interactive text quest set in "
                "{setting_name} ({time_period}). Your job is to COMPILE raw "
                "scene data and event information into readable prose — not to "
                'embellish it. Write in second person ("You see...", "You hear...").\n\n'
                "Faithfulness rules (hard constraints):\n"
                "- Narrate only what the raw material states. Do NOT invent "
                "sensory details (sounds, adjectives, lighting, smells) that are "
                "not explicitly present.\n"
                "- Do NOT invent inner states for NPCs (what they feel, think, or "
                "wait for) unless the raw material names them.\n"
                "- Do NOT invent player reactions or decisions.\n"
                "- If multiple raw bullets describe the same NPC reacting the "
                "same way, summarize them in a single clause — do not serialize "
                "them with 'and then… and then…' cadence.\n"
                "- If the raw material is sparse, keep the narration sparse. "
                "It is better to be short than to pad with plausible-sounding "
                "filler.\n\n"
                "Style guidelines:\n"
                "- Prefer concrete compression over ornamentation.\n"
                "- When NPCs speak, present their dialogue naturally.\n"
                "- On a NEW SCENE: paint a picture of the environment grounded "
                "in the raw material (2-4 paragraphs); sensory detail is allowed "
                "only when it reflects something in the raw data.\n"
                "- On a CONTINUATION (action within the same scene): focus ONLY on "
                "the direct result of the player's action and character reactions. "
                "Do NOT describe the environment, atmosphere, lighting, smells, or "
                "sounds unless the action directly changes them. Keep it short.\n"
                "- When violence occurs, narrate physical consequences honestly — "
                "impacts, injuries, struggle. Do not soften or skip the result of "
                "aggressive actions."
            ),
            required_vars=["setting_name", "time_period"],
        ),
        PromptSection(
            name="time_context",
            template="Time of day: {time_of_day}",
            required_vars=["time_of_day"],
        ),
        PromptSection(
            name="world_mood",
            template=(
                "Current world mood: {world_mood}. Weave this atmosphere into your descriptions "
                "naturally, without naming it explicitly."
            ),
            required_vars=["world_mood"],
        ),
        PromptSection(
            name="language",
            template="Write all your output in {language}.",
            required_vars=["language"],
        ),
        PromptSection(
            name="formatting",
            template=(
                "Format your output using this small Markdown subset:\n"
                "- **bold** — use sparingly, at most one salient element per "
                "paragraph, and only when it materially aids readability. "
                "Do NOT bold every NPC name or object on first mention.\n"
                "- *italic* — for short atmospheric cues or inner thoughts that "
                "are present in the raw material.\n"
                "- `code` for short written text the player reads (signs, letters, inscriptions)\n"
                "- Separate paragraphs with a blank line\n"
                "Do NOT use headings, lists, links, HTML tags, or any other Markdown feature."
            ),
            required_vars=[],
        ),
    ]
)


NARRATOR_NARRATE = PromptTemplate(
    [
        PromptSection(
            name="task",
            template=(
                'Player action: "{player_action}"\n'
                "Scene type: {scene_type}\n\n"
                "Raw material to narrate:\n{raw_material}\n\n"
                "Transform the above into literary narration in second person."
            ),
            required_vars=["player_action", "raw_material", "scene_type"],
        ),
        PromptSection(
            name="events",
            template=(
                "Events that just happened nearby:\n{completed_events}\nWeave these into the narration naturally."
            ),
            required_vars=["completed_events"],
        ),
        PromptSection(
            name="wait_context",
            template=(
                "The player is waiting and observing for roughly {hours_waited} hours. "
                "Describe plausible ambient activity grounded in these threads and "
                "on-shift NPCs:\n{wait_context_lines}\n"
                "Do NOT write 'nothing happens' or 'time passes uneventfully' — "
                "surface motion, sound, routine, and the passage of time."
            ),
            required_vars=["wait_context_lines", "hours_waited"],
        ),
        PromptSection(
            name="turn_intent",
            template=(
                "The player's stated intent for this turn was: {turn_intent}. "
                "Honor this intent in your narration. If the resulting raw material "
                "contradicts the intent (e.g. the player tried to move but the scene "
                "did not change), acknowledge the contradiction explicitly rather than "
                "pretending the intent did not exist."
            ),
            required_vars=["turn_intent"],
        ),
    ]
)


@dataclass(frozen=True)
class NarratorPrompts:
    """Per-locale Narrator prompt bundle.

    ``system`` renders as the Narrator's system prompt (role,
    formatting rules, output language instruction). ``narrate`` is the
    per-turn user message template that carries the raw material.
    """

    system: PromptTemplate
    narrate: PromptTemplate


_CATALOG: types.MappingProxyType[Locale, NarratorPrompts] = types.MappingProxyType(
    {
        Locale.ENGLISH: NarratorPrompts(system=NARRATOR_SYSTEM, narrate=NARRATOR_NARRATE),
        Locale.RUSSIAN: NarratorPrompts(system=NARRATOR_SYSTEM_RU, narrate=NARRATOR_NARRATE_RU),
    }
)


def get_narrator_prompts(language: str | None) -> NarratorPrompts:
    """Return the Narrator prompt bundle for *language*.

    Unrecognised languages transparently fall back to the English
    catalog (see :func:`prompts.locales.resolve_locale`). The returned
    bundle is a module-level singleton — callers must not mutate it.
    """
    return _CATALOG[resolve_locale(language)]
