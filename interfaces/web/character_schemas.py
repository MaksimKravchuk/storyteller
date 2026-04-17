"""Pydantic models for the Character sidebar payload."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

FactSource = Literal["FACT", "RUMOR", "PERSONAL_EXPERIENCE", "HEARSAY"]


class KnownNPC(BaseModel):
    """An NPC the player has been introduced to."""

    name: str
    occupation: str
    descriptor: str


class RememberedFact(BaseModel):
    """A fact the player has personally learned.

    ``source`` is the ``KnowledgeSource`` enum name so the client can
    badge entries without reading the runtime enum module.
    """

    text: str
    source: FactSource


class CharacterInfo(BaseModel):
    """The player-facing Character sidebar payload."""

    name: str
    appearance: str
    physical_status: str
    inventory: list[str]
    known_npcs: list[KnownNPC]
    recent_events: list[str]
    learned_facts: list[RememberedFact]
