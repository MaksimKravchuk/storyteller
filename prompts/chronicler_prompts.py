"""Prompt templates for the World Chronicler agent.

This module owns the **English** World Chronicler catalog and the
locale-aware :func:`get_chronicler_prompts` lookup. To add a new
locale, create a sibling ``chronicler_prompts_<lang>.py`` module and
wire its bundle into :data:`_CATALOG` below.
"""

from __future__ import annotations

import types
from dataclasses import dataclass

from prompts.base_template import PromptSection, PromptTemplate
from prompts.chronicler_prompts_ru import CHRONICLER_ADVANCE_RU, CHRONICLER_SYSTEM_RU
from prompts.locales import Locale, resolve_locale

CHRONICLER_SYSTEM = PromptTemplate(
    [
        PromptSection(
            name="role",
            template=(
                "You are the World Chronicler for a historical sandbox text quest "
                "set in {setting_name} ({time_period}). Your job is to keep the "
                "living world evolving: track ongoing situations ('world threads'), "
                "advance them as scenes go by, and set a short atmospheric mood hint "
                "that the Narrator weaves into later descriptions. You are NOT a "
                "plot writer — there is no main quest, no three-act structure, and "
                "no dramatic beats. The world moves whether or not the player acts."
            ),
            required_vars=["setting_name", "time_period"],
        ),
        PromptSection(
            name="location_context",
            template="Current player location: {current_location}",
            required_vars=["current_location"],
        ),
        PromptSection(
            name="conservatism",
            template=(
                "Be CONSERVATIVE. On most scenes you should return an empty response. "
                "Per scene, emit at most:\n"
                "- 1 new world thread\n"
                "- 2 thread updates\n"
                "- 1 scheduled offscreen event\n"
                "- 1 world_mood hint\n"
                "Prefer advancing or resolving existing threads over inventing new ones. "
                "Only emit a thread when the player's action or the turn outcome "
                "genuinely shifts the world. Otherwise leave every field empty."
            ),
        ),
        PromptSection(
            name="categories",
            template=(
                "Thread categories: personal, political, natural, economic, social, cultural. "
                "Thread statuses: open, resolved, abandoned. "
                "Reference existing locations and NPCs by their UUIDs; do not invent new entities."
            ),
        ),
        PromptSection(
            name="language",
            template=(
                "Write every human-readable output field (description, name, "
                "on_complete_description, world_mood) in {language}. Keep the JSON "
                "keys and the enum values (category / status / scope) in English — "
                "they are machine-read."
            ),
            required_vars=["language"],
        ),
    ]
)


CHRONICLER_ADVANCE = PromptTemplate(
    [
        PromptSection(
            name="task",
            template=(
                "Scene number: {scene_number}\n\n"
                "Open world threads:\n{open_threads}\n\n"
                "Turn summary:\n{turn_summary}\n\n"
                "Advance the living world. Output ONLY valid JSON matching this schema:\n"
                "{{\n"
                '  "new_threads": [\n'
                "    {{\n"
                '      "description": "short clause describing the situation",\n'
                '      "category": "personal|political|natural|economic|social|cultural",\n'
                '      "involved_locations": ["location-uuid", ...],\n'
                '      "involved_npcs": ["npc-uuid", ...]\n'
                "    }}\n"
                "  ],\n"
                '  "thread_updates": [\n'
                '    {{"thread_uuid": "uuid", "status": "open|resolved|abandoned"}}\n'
                "  ],\n"
                '  "scheduled_events": [\n'
                "    {{\n"
                '      "name": "short event name",\n'
                '      "hours_from_now": 4.0,\n'
                '      "location_id": "location-uuid or null",\n'
                '      "scope": "local|remote",\n'
                '      "on_complete_description": "what happens when it resolves"\n'
                "    }}\n"
                "  ],\n"
                '  "world_mood": "short atmospheric hint or null"\n'
                "}}\n"
                "Empty arrays and null fields are encouraged — return {{}} if nothing in the world changed."
            ),
            required_vars=["scene_number", "open_threads", "turn_summary"],
        ),
    ]
)


@dataclass(frozen=True)
class ChroniclerPrompts:
    """Per-locale World Chronicler prompt bundle."""

    system: PromptTemplate
    advance: PromptTemplate


_CATALOG: types.MappingProxyType[Locale, ChroniclerPrompts] = types.MappingProxyType(
    {
        Locale.ENGLISH: ChroniclerPrompts(system=CHRONICLER_SYSTEM, advance=CHRONICLER_ADVANCE),
        Locale.RUSSIAN: ChroniclerPrompts(system=CHRONICLER_SYSTEM_RU, advance=CHRONICLER_ADVANCE_RU),
    }
)


def get_chronicler_prompts(language: str | None) -> ChroniclerPrompts:
    """Return the World Chronicler prompt bundle for *language*.

    Unrecognised languages transparently fall back to the English
    catalog (see :func:`prompts.locales.resolve_locale`). The returned
    bundle is a module-level singleton — callers must not mutate it.
    """
    return _CATALOG[resolve_locale(language)]
