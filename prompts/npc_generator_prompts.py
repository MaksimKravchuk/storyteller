"""Prompt templates for the NPC Generator agent.

This module owns the **English** NPC-generator catalog and the
locale-aware :func:`get_npc_generator_prompts` lookup. Other locales
live in sibling modules (e.g. :mod:`prompts.npc_generator_prompts_ru`)
and register themselves via :data:`_CATALOG` below.
"""

from __future__ import annotations

import types
from dataclasses import dataclass

from prompts.base_template import PromptSection, PromptTemplate
from prompts.locales import Locale, resolve_locale
from prompts.npc_generator_prompts_ru import NPC_GENERATOR_CREATE_RU, NPC_GENERATOR_SYSTEM_RU

NPC_GENERATOR_SYSTEM = PromptTemplate(
    [
        PromptSection(
            name="role",
            template=(
                "You are an NPC Generator for an interactive text quest. "
                "You create detailed, historically plausible character cards. "
                "Each NPC should feel like a real person with their own life, "
                "goals, and limitations — not a plot device."
            ),
        ),
        PromptSection(
            name="setting",
            template=("Setting: {setting_summary}\nLocation: {location_name}\nSocial structure: {social_structure}"),
            required_vars=["setting_summary", "location_name", "social_structure"],
        ),
        PromptSection(
            name="language",
            template=(
                "Fill every human-readable text field (name, biography, appearance, "
                "short_descriptor, occupation, personality_traits, speech_style, "
                "inventory) in {language}. Keep the JSON keys and enum values "
                "(knowledge_scope, attributes dict keys) in English — they are "
                "machine-read."
            ),
            required_vars=["language"],
        ),
    ]
)


NPC_GENERATOR_CREATE = PromptTemplate(
    [
        PromptSection(
            name="task",
            template=(
                "Create an NPC: {npc_request}\n\n"
                "Output ONLY valid JSON with these fields:\n"
                "{{\n"
                '  "name": "A historically appropriate name",\n'
                '  "biography": "2-3 sentences of backstory",\n'
                '  "appearance": "Physical description, clothing, distinguishing features",\n'
                '  "short_descriptor": "One visible-features phrase a stranger would notice '
                "at a glance (≤80 chars). Must NOT include the NPC's name or occupation title. "
                "Example: 'a stocky woman in a bloodstained apron'.\",\n"
                '  "occupation": "Their trade or role",\n'
                '  "personality_traits": ["trait1", "trait2", "trait3"],\n'
                '  "speech_style": "Describe HOW they speak, never WHAT they say. '
                "Cover: register (formal/casual/coarse), vocabulary level (learned/plain/rustic), "
                "sentence rhythm (clipped/flowing/rambling), and emotional control "
                "(measured/volatile/dry). Do NOT include verbatim example phrases, "
                'catchphrases, or quoted lines they ‘typically say’.",\n'
                '  "knowledge_scope": "local|city|region|country|world",\n'
                '  "attributes": {{\n'
                '    "education": 0-10,\n'
                '    "social_status": 0-10,\n'
                '    "friendliness": 0-10,\n'
                '    "suspicion": 0-10,\n'
                '    "combat_skill": 0-10,    // 0=helpless, 3=average, 7=trained soldier, 10=elite warrior\n'
                '    "persuasion_skill": 0-10, // 0=unconvincing, 5=average, 10=master diplomat\n'
                '    "deception_skill": 0-10,  // 0=transparent, 5=average, 10=consummate liar\n'
                '    "intimidation_skill": 0-10, // 0=meek, 5=average, 10=terrifying\n'
                '    "perception_skill": 0-10, // 0=oblivious, 5=average, 10=nothing escapes them\n'
                '    "stealth_skill": 0-10     // 0=clumsy, 5=average, 10=shadow\n'
                "  }},\n"
                '  "inventory": ["items they carry or sell"]\n'
                "}}"
            ),
            required_vars=["npc_request"],
        ),
        PromptSection(
            name="forbidden_names",
            template=(
                "The following names are already used by other characters in this scene — "
                "pick a clearly different full name (distinct first AND last name) for this NPC:\n"
                "{forbidden_names}"
            ),
            required_vars=["forbidden_names"],
        ),
    ]
)


@dataclass(frozen=True)
class NPCGeneratorPrompts:
    """Per-locale NPC-generator prompt bundle.

    ``system`` renders as the NPC Generator's system prompt (role,
    setting, output-language instruction). ``create`` is the per-request
    user message template that names the NPC role and spells out the
    JSON schema the LLM must return.
    """

    system: PromptTemplate
    create: PromptTemplate


_CATALOG: types.MappingProxyType[Locale, NPCGeneratorPrompts] = types.MappingProxyType(
    {
        Locale.ENGLISH: NPCGeneratorPrompts(system=NPC_GENERATOR_SYSTEM, create=NPC_GENERATOR_CREATE),
        Locale.RUSSIAN: NPCGeneratorPrompts(system=NPC_GENERATOR_SYSTEM_RU, create=NPC_GENERATOR_CREATE_RU),
    }
)


def get_npc_generator_prompts(language: str | None) -> NPCGeneratorPrompts:
    """Return the NPC-generator prompt bundle for *language*.

    Unrecognised languages transparently fall back to the English
    catalog (see :func:`prompts.locales.resolve_locale`). The returned
    bundle is a module-level singleton — callers must not mutate it.
    """
    return _CATALOG[resolve_locale(language)]
