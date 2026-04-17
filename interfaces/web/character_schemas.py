"""Pydantic models for the Character sidebar payload.

Split out of ``schemas.py`` so that module stays under the wemake
``WPS202 too many module members`` cap. The types are re-exported from
``schemas`` for backwards compatibility with existing imports.
"""

from __future__ import annotations

from pydantic import BaseModel


class KnownNPC(BaseModel):
    """An NPC the player has been introduced to."""

    name: str
    occupation: str
    descriptor: str


class RememberedFact(BaseModel):
    """A fact the player has personally learned.

    ``source`` is the ``KnowledgeSource`` enum name (``FACT`` / ``RUMOR`` /
    ``PERSONAL_EXPERIENCE`` / ``HEARSAY``) so the client can badge entries
    without reading the runtime enum module.
    """

    text: str
    source: str


class CharacterInfo(BaseModel):
    """The player-facing Character sidebar payload."""

    name: str
    appearance: str
    physical_status: str
    inventory: list[str]
    known_npcs: list[KnownNPC]
    recent_events: list[str]
    learned_facts: list[RememberedFact]
