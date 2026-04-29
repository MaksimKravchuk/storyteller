"""Prompt templates for the Item Generator agent.

This module owns the **English** Item Generator catalog and the
locale-aware :func:`get_item_generator_prompts` lookup. To add a new
locale, create a sibling ``item_generator_prompts_<lang>.py`` module
and wire its bundle into :data:`_CATALOG` below.
"""

from __future__ import annotations

import types
from dataclasses import dataclass

from prompts.base_template import PromptSection, PromptTemplate
from prompts.item_generator_prompts_ru import (
    ITEM_GENERATOR_BATCH_RU,
    ITEM_GENERATOR_EXAMINE_RU,
    ITEM_GENERATOR_INTERACT_RU,
    ITEM_GENERATOR_SYSTEM_RU,
)
from prompts.locales import Locale, resolve_locale

ITEM_GENERATOR_SYSTEM = PromptTemplate(
    [
        PromptSection(
            name="role",
            template=(
                "You are an Item Generator for an interactive text quest. "
                "You produce precise, physical descriptions of objects — weapons, tools, "
                "goods, clothing, containers, and other items.\n"
                "STRICT RULES:\n"
                "- Describe ONLY physical properties: material, dimensions, weight, "
                "condition, wear marks, construction method.\n"
                "- NO literary flourishes. NO 'beautifully crafted', 'gleaming in the light', "
                "'ornately decorated'. State facts.\n"
                "- NO backstory or history unless explicitly requested.\n"
                "- Use period-appropriate terminology for the setting.\n"
                "- Format each item as: Name (material, key dimensions, condition, notable features)."
            ),
        ),
        PromptSection(
            name="setting",
            template="Setting: {setting_summary}",
            required_vars=["setting_summary"],
        ),
        PromptSection(
            name="language",
            template=(
                "Write every human-readable output field (items, description, "
                "narration, delta) in {language}. Keep the JSON keys in English "
                "— they are machine-read."
            ),
            required_vars=["language"],
        ),
    ]
)


ITEM_GENERATOR_BATCH = (
    "Expand these bare item names into precise physical descriptions.\n"
    "Owner context: {owner_context}\n\n"
    "Items to describe:\n{item_list}\n\n"
    "Output ONLY valid JSON:\n"
    "{{\n"
    '  "items": [\n'
    '    "ItemName (material, dimensions, condition, features)",\n'
    '    "...one entry per input item, same order..."\n'
    "  ]\n"
    "}}\n\n"
    "Keep each description under 120 characters. Be factual and specific."
)


ITEM_GENERATOR_EXAMINE = (
    "Produce a detailed physical examination of this item.\n"
    "Item: {item_name}\n"
    "Context: {context_hint}\n\n"
    "Output ONLY valid JSON:\n"
    "{{\n"
    '  "description": "Detailed physical description: material, construction, '
    'dimensions, weight estimate, condition, wear patterns, maker marks if visible."\n'
    "}}\n\n"
    "Be precise and factual. 2-4 sentences maximum."
)


ITEM_GENERATOR_INTERACT = (
    "The player physically interacts with an object in the current scene. "
    "Describe what happens to the object, and produce the persistent state change.\n"
    'Player action: "{player_action}"\n'
    "Object: {object_name}\n"
    "Scene context: {context_hint}\n\n"
    "Output ONLY valid JSON:\n"
    "{{\n"
    '  "narration": "Short factual description of what physically happens '
    '(2-3 sentences, no literary flourishes).",\n'
    '  "delta": "One factual sentence describing the persistent state change '
    "(e.g. 'The window is broken.', 'The torch is lit.'). "
    "Empty string if the interaction leaves no lasting change (e.g. bumping "
    'into a wall)."\n'
    "}}\n\n"
    "Be strictly physical — describe changes a later observer could detect."
)


@dataclass(frozen=True)
class ItemGeneratorPrompts:
    """Per-locale Item Generator prompt bundle."""

    system: PromptTemplate
    batch: str
    examine: str
    interact: str


_CATALOG: types.MappingProxyType[Locale, ItemGeneratorPrompts] = types.MappingProxyType(
    {
        Locale.ENGLISH: ItemGeneratorPrompts(
            system=ITEM_GENERATOR_SYSTEM,
            batch=ITEM_GENERATOR_BATCH,
            examine=ITEM_GENERATOR_EXAMINE,
            interact=ITEM_GENERATOR_INTERACT,
        ),
        Locale.RUSSIAN: ItemGeneratorPrompts(
            system=ITEM_GENERATOR_SYSTEM_RU,
            batch=ITEM_GENERATOR_BATCH_RU,
            examine=ITEM_GENERATOR_EXAMINE_RU,
            interact=ITEM_GENERATOR_INTERACT_RU,
        ),
    }
)


def get_item_generator_prompts(language: str | None) -> ItemGeneratorPrompts:
    """Return the Item Generator prompt bundle for *language*.

    Unrecognised languages transparently fall back to the English
    catalog (see :func:`prompts.locales.resolve_locale`). The returned
    bundle is a module-level singleton — callers must not mutate it.
    """
    return _CATALOG[resolve_locale(language)]
