"""Schema for the NPC-generator LLM JSON response."""

from __future__ import annotations

from pydantic import BaseModel, Field


class NPCAttributes(BaseModel):
    """Fixed-key NPC skill/stat block the LLM fills in.

    OpenAI strict-mode structured outputs reject free-form ``dict[str, int]``
    (a JSON-Schema ``type: object`` with ``additionalProperties: {...}`` and
    no ``properties``). Enumerating the keys as typed fields emits a schema
    with ``additionalProperties: false`` and passes validation. The set of
    keys mirrors the NPC-generator prompt.
    """

    education: int = 0
    social_status: int = 0
    friendliness: int = 0
    suspicion: int = 0
    combat_skill: int = 0
    persuasion_skill: int = 0
    deception_skill: int = 0
    intimidation_skill: int = 0
    perception_skill: int = 0
    stealth_skill: int = 0


class NPCResponse(BaseModel):
    """Typed view of the fields the LLM produces for a single NPC card.

    Field defaults mirror the ``.get(key, default)`` semantics of the
    original ``cast/npc_generator.py`` code. ``uuid`` and ``location_id``
    are intentionally absent — those are stamped by the generator
    caller from the current game state, not by the LLM.
    """

    name: str = "Unknown"
    biography: str = ""
    appearance: str = ""
    short_descriptor: str = ""
    occupation: str = ""
    personality_traits: list[str] = Field(default_factory=list)
    speech_style: str = "neutral"
    knowledge_scope: str = "local"
    attributes: NPCAttributes = Field(default_factory=NPCAttributes)
    inventory: list[str] = Field(default_factory=list)
