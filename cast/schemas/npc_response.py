"""Schema for the NPC-generator LLM JSON response."""

from __future__ import annotations

from pydantic import BaseModel, Field


class NPCAttributes(BaseModel):
    """Fixed-key NPC skill/stat block the LLM fills in.

    Strict-mode structured outputs reject free-form ``dict[str, int]``
    because ``_StrictSchemaNormalizer`` only anchors
    ``additionalProperties: false`` onto nodes that expose explicit
    ``properties``. Enumerating the keys as typed fields gives the
    normalizer something to clamp; the set mirrors the NPC-generator
    prompt, which specifies a 0-10 scale.
    """

    education: int = Field(default=0, ge=0, le=10)
    social_status: int = Field(default=0, ge=0, le=10)
    friendliness: int = Field(default=0, ge=0, le=10)
    suspicion: int = Field(default=0, ge=0, le=10)
    combat_skill: int = Field(default=0, ge=0, le=10)
    persuasion_skill: int = Field(default=0, ge=0, le=10)
    deception_skill: int = Field(default=0, ge=0, le=10)
    intimidation_skill: int = Field(default=0, ge=0, le=10)
    perception_skill: int = Field(default=0, ge=0, le=10)
    stealth_skill: int = Field(default=0, ge=0, le=10)


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
