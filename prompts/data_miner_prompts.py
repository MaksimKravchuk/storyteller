"""Prompt templates for the Data Miner agent.

This module owns the **English** Data Miner catalog and the
locale-aware :func:`get_data_miner_prompts` lookup. To add a new
locale, create a sibling ``data_miner_prompts_<lang>.py`` module and
wire its bundle into the ``make_locale_lookup`` call below.
"""

from __future__ import annotations

from dataclasses import dataclass

from prompts.base_template import PromptSection, PromptTemplate
from prompts.data_miner_prompts_ru import (
    DATA_MINER_RESEARCH_RU,
    DATA_MINER_SEARCH_TERMS_RU,
    DATA_MINER_SYSTEM_RU,
)
from prompts.locales import Locale, make_locale_lookup

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


DATA_MINER_SEARCH_TERMS = (
    "The player wants a game setting based on:\n"
    '"{setting_request}"\n\n'
    "Generate a JSON list of 3-8 Wikipedia search terms that would "
    "give us the best historical context for this setting.\n"
    "Output ONLY a JSON object: "
    '{{"search_terms": ["term1", "term2", ...]}}'
)


DATA_MINER_RESEARCH = (
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
)


@dataclass(frozen=True)
class DataMinerPrompts:
    """Per-locale Data Miner prompt bundle."""

    system: PromptTemplate
    search_terms: str
    research: str


get_data_miner_prompts = make_locale_lookup(
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
