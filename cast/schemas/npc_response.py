"""Schema for the NPC-generator LLM JSON response."""

from __future__ import annotations

from pydantic import BaseModel, Field


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
    attributes: dict[str, int] = Field(default_factory=dict)
    inventory: list[str] = Field(default_factory=list)
