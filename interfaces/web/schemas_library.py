"""Pydantic models for the web story library API."""

from __future__ import annotations

from pydantic import BaseModel


class PlaybillCastMember(BaseModel):
    """One name on the playbill, already name-gated like ``ScenePerson.label``."""

    label: str
    known: bool


class Playbill(BaseModel):
    """The story's poster copy, captured deterministically after the prologue.

    ``tagline`` is the opening's first sentence; ``cast`` comes from the
    scene's people (``NPCCard.label_for_player``); ``place_type`` and
    ``daypart`` reuse the backend slugs the client already draws as icons.
    ``hero`` is None for an unnamed player; ``hero_look`` feeds the optional
    illustration prompt.
    """

    tagline: str
    setting: str
    hero: str | None
    hero_look: str
    era: str
    region: str
    place: str | None
    place_type: str
    daypart: str
    cast: list[PlaybillCastMember]


class GameSummary(BaseModel):
    """Compact library row for one caller-owned story."""

    game_id: str
    title: str
    setting: str
    turn_count: int
    playbill: Playbill | None = None
    has_poster_image: bool = False


class GameListResponse(BaseModel):
    """Response body for ``GET /api/games``."""

    games: list[GameSummary]
