"""Prompt templates for the Data Miner agent.

This module owns the **English** Data Miner catalog and the
locale-aware :func:`get_data_miner_prompts` lookup. Other locales live
in sibling modules (e.g. :mod:`prompts.data_miner_prompts_ru`) and
register themselves via :data:`_CATALOG` below.
"""

from __future__ import annotations

import types
from dataclasses import dataclass

from prompts.base_template import PromptSection, PromptTemplate
from prompts.data_miner_prompts_ru import (
    DATA_MINER_RESEARCH_RU,
    DATA_MINER_SEARCH_TERMS_RU,
    DATA_MINER_SYSTEM_RU,
)
from prompts.locales import Locale, resolve_locale

DATA_MINER_SYSTEM = PromptTemplate(
    [
        PromptSection(
            name="role",
            template=(
                "You are a historical research specialist for an interactive "
                "text quest. Your job is to synthesise raw Wikipedia excerpts "
                "into a structured game setting. Be accurate to real history "
                "but fill in plausible details where sources are thin."
            ),
        ),
        PromptSection(
            name="language",
            template=(
                "Write every human-readable output field (name, time_period, "
                "region, summary, role, description, traditions, social_structure) "
                "in {language}. Keep JSON keys in English — they are machine-read. "
                "Wikipedia search terms (search_terms) should remain in whatever "
                "form matches the English-language Wikipedia article titles."
            ),
            required_vars=["language"],
        ),
    ]
)


DATA_MINER_SEARCH_TERMS = PromptTemplate(
    [
        PromptSection(
            name="task",
            template=(
                "The player wants a game setting based on:\n"
                '"{setting_request}"\n\n'
                "Generate a JSON list of 3-8 Wikipedia search terms that would "
                "give us the best historical context for this setting.\n"
                "Output ONLY a JSON object: "
                '{{"search_terms": ["term1", "term2", ...]}}'
            ),
            required_vars=["setting_request"],
        ),
    ]
)


DATA_MINER_RESEARCH = PromptTemplate(
    [
        PromptSection(
            name="task",
            template=(
                "Setting request: {setting_request}\n\n"
                "Raw Wikipedia research:\n{raw_research}\n\n"
                "Synthesise this into a structured game setting. "
                "Output ONLY valid JSON with these fields:\n"
                "{{\n"
                '  "name": "Setting name",\n'
                '  "time_period": "e.g. 1st century AD",\n'
                '  "region": "e.g. Roman Empire, Italia",\n'
                '  "summary": "2-3 paragraph overview",\n'
                '  "key_persons": [{{"name": "...", "role": "...", "description": "..."}}],\n'
                '  "key_events": [{{"name": "...", "date": "...", "description": "..."}}],\n'
                '  "locations": [{{"name": "...", "type": "...", "description": "..."}}],\n'
                '  "traditions": ["..."],\n'
                '  "technologies": ["..."],\n'
                '  "social_structure": "Description of social hierarchy"\n'
                "}}"
            ),
            required_vars=["setting_request", "raw_research"],
        ),
    ]
)


@dataclass(frozen=True)
class DataMinerPrompts:
    """Per-locale Data Miner prompt bundle."""

    system: PromptTemplate
    search_terms: PromptTemplate
    research: PromptTemplate


_CATALOG: types.MappingProxyType[Locale, DataMinerPrompts] = types.MappingProxyType(
    {
        Locale.ENGLISH: DataMinerPrompts(
            system=DATA_MINER_SYSTEM,
            search_terms=DATA_MINER_SEARCH_TERMS,
            research=DATA_MINER_RESEARCH,
        ),
        Locale.RUSSIAN: DataMinerPrompts(
            system=DATA_MINER_SYSTEM_RU,
            search_terms=DATA_MINER_SEARCH_TERMS_RU,
            research=DATA_MINER_RESEARCH_RU,
        ),
    }
)


def get_data_miner_prompts(language: str | None) -> DataMinerPrompts:
    """Return the Data Miner prompt bundle for *language*.

    Unrecognised languages transparently fall back to the English
    catalog (see :func:`prompts.locales.resolve_locale`). The returned
    bundle is a module-level singleton — callers must not mutate it.
    """
    return _CATALOG[resolve_locale(language)]
