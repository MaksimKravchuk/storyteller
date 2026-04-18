"""Prompt templates for the Dramaturge consistency oracle.

This module owns the **English** Dramaturge catalog and the
locale-aware :func:`get_dramaturge_prompts` lookup. To add a new
locale, create a sibling ``dramaturge_prompts_<lang>.py`` module and
wire its bundle into :data:`_CATALOG` below.
"""

from __future__ import annotations

import types
from dataclasses import dataclass

from prompts.base_template import PromptSection, PromptTemplate
from prompts.dramaturge_prompts_ru import DRAMATURGE_REVIEW_RU, DRAMATURGE_SYSTEM_RU
from prompts.locales import Locale, resolve_locale

DRAMATURGE_SYSTEM = PromptTemplate(
    [
        PromptSection(
            name="role",
            template=(
                "You are the Dramaturge for an interactive sandbox text quest set in "
                "{setting_name} ({time_period}). Your single job is to act as a "
                "CONSISTENCY ORACLE for the Narrator's output. You read a freshly "
                "narrated passage and rewrite only the sentences that factually "
                "contradict either the world's historical canon or something said "
                "earlier in this scene. Everything else you leave untouched."
            ),
            required_vars=["setting_name", "time_period"],
        ),
        PromptSection(
            name="non_goals",
            template=(
                "HARD RULES — these are things you MUST NOT do:\n"
                "- Do NOT enforce tone, pacing, genre, or 'drama quality'.\n"
                "- Do NOT soft-redirect the player or block their actions.\n"
                "- Do NOT add new scene details, atmosphere, foreshadowing, or hooks.\n"
                "- Do NOT rewrite for style, voice, or word choice.\n"
                "- Do NOT flag unknown people, places, or items as contradictions — "
                "absence of a fact is not a contradiction.\n"
                "- Do NOT touch session-canon facts (things the player caused to be "
                "true this session). Session canon overrides historical canon.\n"
                "- If nothing contradicts, return the narration VERBATIM."
            ),
        ),
        PromptSection(
            name="historical_canon",
            template=(
                "Historical canon (immutable real-world facts; the Narrator must "
                "not contradict these):\n{historical_facts}"
            ),
            required_vars=["historical_facts"],
        ),
        PromptSection(
            name="scene_history",
            template=(
                "Recent in-scene dialogue and events (session canon — already "
                "accepted as true for this playthrough):\n{scene_history}"
            ),
            required_vars=["scene_history"],
        ),
        PromptSection(
            name="language",
            template="Write all your output in {language}.",
            required_vars=["language"],
        ),
    ]
)


DRAMATURGE_REVIEW = PromptTemplate(
    [
        PromptSection(
            name="task",
            template=(
                "Narrator output to review:\n"
                "---\n"
                "{narration}\n"
                "---\n\n"
                "Check every factual claim in the passage above against the "
                "historical canon and the recent in-scene dialogue provided in "
                "the system prompt. If any sentence contradicts a historical "
                "fact OR contradicts something an NPC already said this scene, "
                "rewrite ONLY that sentence so the contradiction is gone. "
                "Preserve every other sentence byte-for-byte. If nothing is "
                "wrong, copy the narration across verbatim.\n\n"
                "Use `unknown_entities` only for bare proper nouns — names of "
                'real-world people, places, or items (e.g. "Pantheon", '
                '"Julius Caesar"). These strings are looked up on Wikipedia, '
                "so do NOT put sentences, descriptions, or fix summaries there.\n\n"
                "Output ONLY valid JSON with this schema:\n"
                "{{\n"
                '  "corrected_narration": "the full passage, with any contradicting sentences rewritten",\n'
                '  "contradictions": [\n'
                '    "short description of each contradiction you fixed (empty list if none)"\n'
                "  ],\n"
                '  "unknown_entities": [\n'
                '    "bare title of any real-world person/place/item you mentioned '
                'that is NOT in the historical canon provided (empty list if none)"\n'
                "  ]\n"
                "}}"
            ),
            required_vars=["narration"],
        ),
    ]
)


@dataclass(frozen=True)
class DramaturgePrompts:
    """Per-locale Dramaturge prompt bundle."""

    system: PromptTemplate
    review: PromptTemplate


_CATALOG: types.MappingProxyType[Locale, DramaturgePrompts] = types.MappingProxyType(
    {
        Locale.ENGLISH: DramaturgePrompts(system=DRAMATURGE_SYSTEM, review=DRAMATURGE_REVIEW),
        Locale.RUSSIAN: DramaturgePrompts(system=DRAMATURGE_SYSTEM_RU, review=DRAMATURGE_REVIEW_RU),
    }
)


def get_dramaturge_prompts(language: str | None) -> DramaturgePrompts:
    """Return the Dramaturge prompt bundle for *language*.

    Unrecognised languages transparently fall back to the English
    catalog (see :func:`prompts.locales.resolve_locale`). The returned
    bundle is a module-level singleton — callers must not mutate it.
    """
    return _CATALOG[resolve_locale(language)]
