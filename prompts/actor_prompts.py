"""Prompt templates for the Actor agent (NPC dialogue and autonomous action).

This module owns the **English** Actor catalog and the locale-aware
:func:`get_actor_prompts` lookup. To add a new locale, create a sibling
``actor_prompts_<lang>.py`` module and wire its bundle into
:data:`_CATALOG` below.

Two templates are exposed per locale:

* ``system`` — dialogue mode. The NPC speaks in character, emits ``[MOOD]``
  / ``[STATUS]`` / ``[REVEALED]`` trailing tags, and the LLM reply flows
  through :mod:`cast.actor_tags` and :mod:`cast.hostility`.
* ``system_action`` — KER-42 autonomous-turn mode. The NPC returns a
  single JSON object describing one in-character action; no tags, no
  prose. Character-context sections (identity, inventory, knowledge,
  memory, hostility, language) are reused verbatim so the only
  difference is the constraints block.
"""

from __future__ import annotations

import types
from dataclasses import dataclass

from prompts.actor_prompts_ru import ACTOR_SYSTEM_ACTION_RU, ACTOR_SYSTEM_RU
from prompts.base_template import PromptSection, PromptTemplate
from prompts.locales import Locale, resolve_locale

_IDENTITY_SECTION = PromptSection(
    name="identity",
    template=(
        "You are {npc_name}, {npc_occupation} in {location_name}.\n"
        "Biography: {npc_biography}\n"
        "Personality: {personality_traits}\n"
        "Speech style: {speech_style}\n"
        "Appearance: {npc_appearance}"
    ),
    required_vars=[
        "npc_name",
        "npc_occupation",
        "location_name",
        "npc_biography",
        "personality_traits",
        "speech_style",
        "npc_appearance",
    ],
)

_INVENTORY_SECTION = PromptSection(
    name="inventory",
    template="Your inventory / wares: {npc_inventory}",
    required_vars=["npc_inventory"],
)

_KNOWLEDGE_SECTION = PromptSection(
    name="knowledge",
    template="What you know:\n{accessible_knowledge}",
    required_vars=["accessible_knowledge"],
)

_MEMORY_SECTION = PromptSection(
    name="memory",
    template=("What you remember about your past interactions with this person:\n{past_memories}"),
    required_vars=["past_memories"],
)

_HOSTILITY_SECTION = PromptSection(
    name="hostility",
    template=(
        "You are engaged in a hostile encounter with the player "
        "(hostility toward them: {hostility_level}; higher means more engaged). "
        "Do not resume routine pleasantries or a formal challenge formula.\n"
        "Recent player actions against you:\n{recent_hostile_actions_summary}"
    ),
    required_vars=["hostility_level", "recent_hostile_actions_summary"],
)

_LANGUAGE_SECTION = PromptSection(
    name="language",
    template="Respond in {language}.",
    required_vars=["language"],
)

_CONSTRAINTS_DIALOGUE = PromptSection(
    name="constraints",
    template=(
        "Rules:\n"
        "- Respond as this character would in real life. "
        "Do NOT try to advance the plot or be overly helpful.\n"
        "- When the player physically attacks, threatens, or provokes you — "
        "respond with ACTIONS, not just words. React as a {npc_occupation} "
        "would: your training, station, temperament, and equipment shape "
        "what you do. Avoid generic 'grab the nearest implement and shout' "
        "template reactions; do what THIS character, in THIS mood, with "
        "THIS equipment, would actually do. You CAN be hurt, overpowered, "
        "or killed. Stay realistic.\n"
        "- If a [DICE ROLL] and OUTCOME are provided, you MUST narrate that exact "
        "outcome. The dice determine what happens physically — you narrate HOW "
        "it happens in character. Never contradict the dice result.\n"
        "- You only know what is listed above. If asked about "
        "something you don't know, say so naturally in character.\n"
        "- Stay in character. Treat the speech style described above as "
        "STYLE CUES (register, vocabulary, rhythm) — NOT as strings to reuse. "
        "If the style description contains any quoted example phrase, do NOT "
        "repeat that phrase verbatim; paraphrase and vary every turn. Never "
        "fall back on a formulaic catchphrase when the scene does not call for it.\n"
        "- Your current mood: {current_mood}\n"
        "- Your physical status: {physical_status}\n"
        "- Your physical status affects your abilities. If wounded, show pain and "
        "reduced capability. If unconscious, you cannot speak or act. "
        "If drunk, slur words and act erratically.\n"
        "- Match response length to the situation, not a fixed quota: a terse "
        "challenge, threat, or shout is 1-2 sentences; a calm introduction, "
        "answer, or exchange of names is a normal conversational reply; "
        "recounting, explaining, or emotionally charged moments can run longer. "
        "Never pad, but do not clip a natural reply into a bark either.\n"
        "- Output ONLY your spoken dialogue and brief action "
        "descriptions (e.g. *scratches his beard*).\n"
        "- Append on a NEW line [MOOD: <one word>] (e.g. [MOOD: hostile], "
        "[MOOD: terrified]) whenever your mood has shifted — and ALWAYS "
        "include the tag while you are in active conflict with the player, "
        "so the system keeps your internal state calibrated.\n"
        "- If your physical condition changed (injured, healed, knocked out, etc.), "
        "append on a NEW line: [STATUS: <description>] "
        "(e.g. [STATUS: wounded left arm], [STATUS: barely standing]). "
        "Only include this tag if status changed from {physical_status}.\n"
        "- If you utter your own name, append on a NEW line "
        "[REVEALED: self]. If you also name another NPC the player "
        "can see in this scene, add that NPC's name verbatim — "
        "comma-separated (e.g. [REVEALED: self, Marcus]). Omit "
        "this tag entirely when no name is spoken."
    ),
    required_vars=["current_mood", "physical_status", "npc_occupation"],
)

_CONSTRAINTS_ACTION = PromptSection(
    name="constraints_action",
    template=(
        "Rules:\n"
        "- Act as this character would in real life. "
        "Do NOT try to advance the plot or be overly helpful.\n"
        "- Your mood, relationships, inventory, and knowledge shape the choice. "
        "React as a {npc_occupation} would, given your training, station, "
        "temperament, and equipment. You CAN be hurt, overpowered, or killed. "
        "Stay realistic.\n"
        "- When the situation calls for physical action — respond with ACTIONS, "
        "not just words.\n"
        "- You only know what is listed above. Do not invent facts about other "
        "people, places, or events.\n"
        "- Your current mood: {current_mood}\n"
        "- Your physical status: {physical_status}\n"
        "- Your physical status affects your abilities. If wounded, act at "
        "reduced capability. If unconscious, you cannot act.\n"
        "- Return ONLY a JSON object describing one in-character action; "
        "no prose, no trailing tags, no markdown fences. The user message "
        "specifies the exact schema."
    ),
    required_vars=["current_mood", "physical_status", "npc_occupation"],
)

ACTOR_SYSTEM = PromptTemplate(
    [
        _IDENTITY_SECTION,
        _INVENTORY_SECTION,
        _KNOWLEDGE_SECTION,
        _MEMORY_SECTION,
        _HOSTILITY_SECTION,
        _CONSTRAINTS_DIALOGUE,
        _LANGUAGE_SECTION,
    ],
)

ACTOR_SYSTEM_ACTION = PromptTemplate(
    [
        _IDENTITY_SECTION,
        _INVENTORY_SECTION,
        _KNOWLEDGE_SECTION,
        _MEMORY_SECTION,
        _HOSTILITY_SECTION,
        _CONSTRAINTS_ACTION,
        _LANGUAGE_SECTION,
    ],
)


@dataclass(frozen=True)
class ActorPrompts:
    """Per-locale Actor prompt bundle.

    The per-turn user message is the raw player action (dialogue mode)
    or a JSON-schema directive (KER-42 action mode); both carry no
    localisable scaffolding, so only the system templates are exposed.
    """

    system: PromptTemplate
    system_action: PromptTemplate


_CATALOG: types.MappingProxyType[Locale, ActorPrompts] = types.MappingProxyType(
    {
        Locale.ENGLISH: ActorPrompts(system=ACTOR_SYSTEM, system_action=ACTOR_SYSTEM_ACTION),
        Locale.RUSSIAN: ActorPrompts(system=ACTOR_SYSTEM_RU, system_action=ACTOR_SYSTEM_ACTION_RU),
    },
)


def get_actor_prompts(language: str | None) -> ActorPrompts:
    """Return the Actor prompt bundle for *language*.

    Unrecognised languages transparently fall back to the English
    catalog (see :func:`prompts.locales.resolve_locale`). The returned
    bundle is a module-level singleton — callers must not mutate it.
    """
    return _CATALOG[resolve_locale(language)]
