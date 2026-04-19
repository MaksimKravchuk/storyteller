"""Pydantic request/response models for the web API.

This is the contract that any client (web, PWA, native mobile) consumes,
so keep it small, stable, and free of implementation details. Helpers that
build/serialize values live in ``transcript.py``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from interfaces.web.character_schemas import CharacterInfo
from models.visible_entity import VisibleEntity

_SETTING_MAX_CHARS = 500
_ACTION_MAX_CHARS = 2000
_DEFAULT_LANGUAGE = "English"


class StartGameRequest(BaseModel):
    """Body for ``POST /api/games``."""

    setting: str = Field(min_length=1, max_length=_SETTING_MAX_CHARS)
    language: str = _DEFAULT_LANGUAGE


class ActionRequest(BaseModel):
    """Body for ``POST /api/games/{game_id}/actions``."""

    action: str = Field(min_length=1, max_length=_ACTION_MAX_CHARS)


class TurnEntry(BaseModel):
    """One line in the transcript — either player input or narrator prose.

    ``text`` is the raw value as the engine produced it (player input verbatim,
    narrator output as the LLM emitted it, including the ``**bold**`` /
    ``*italic*`` / ```` `code` ```` markdown subset). ``html`` is the same
    content already rendered to safe HTML so a browser client can drop it
    into ``innerHTML`` directly: player text is escaped, narrator text is
    rendered through ``formatting.markdown_render.to_html``.

    ``visible_entities`` is the per-turn chip payload — NPCs, points of
    interest and tracked items the player can see on this narrator line.
    Player rows leave it empty.
    """

    role: Literal["player", "narrator"]
    text: str
    html: str
    visible_entities: list[VisibleEntity] = Field(default_factory=list)


class GameSnapshot(BaseModel):
    """The full view a client needs to render the game on load or after start.

    The opening narration is the first narrator entry in ``transcript``.
    """

    game_id: str
    setting: str
    transcript: list[TurnEntry]
    turn_count: int
    character: CharacterInfo


class ActionResponse(BaseModel):
    """Response body for ``POST /api/games/{game_id}/actions``.

    ``narration`` is the raw markdown text the engine produced;
    ``narration_html`` is the same value pre-rendered for browser clients.
    ``visible_entities`` carries the chip payload for the rendered turn.
    """

    narration: str
    narration_html: str
    turn_count: int
    character: CharacterInfo
    visible_entities: list[VisibleEntity] = Field(default_factory=list)
