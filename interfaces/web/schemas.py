"""Pydantic request/response models for the web API.

This is the contract that any client (web, PWA, native mobile) consumes,
so keep it small, stable, and free of implementation details. Helpers that
build/serialize values live in ``transcript.py``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from interfaces.web.character_schemas import CharacterInfo

_SETTING_MAX_CHARS = 500
_ACTION_MAX_CHARS = 2000
_DEFAULT_LANGUAGE = "English"
_NAME_MAX_CHARS = 128
_APPEARANCE_MAX_CHARS = 500
_INVENTORY_MAX_ITEMS = 20
_INVENTORY_ITEM_MAX_CHARS = 64


class CharacterCreationInput(BaseModel):
    """Body field on ``StartGameRequest`` carrying the player's character.

    All fields are optional; an absent or fully-empty payload preserves
    the engine's anonymous defaults.
    """

    name: str = Field(default="", max_length=_NAME_MAX_CHARS)
    appearance: str = Field(default="", max_length=_APPEARANCE_MAX_CHARS)
    inventory: list[str] = Field(default_factory=list, max_length=_INVENTORY_MAX_ITEMS)

    @field_validator("inventory")
    @classmethod
    def _strip_and_drop_empty(cls, raw_items: list[str]) -> list[str]:
        """Trim each item and drop anything that's empty after trimming."""
        cleaned: list[str] = []
        for raw in raw_items:
            trimmed = raw.strip()
            if not trimmed:
                continue
            if len(trimmed) > _INVENTORY_ITEM_MAX_CHARS:
                raise ValueError(
                    f"Inventory item exceeds {_INVENTORY_ITEM_MAX_CHARS} characters",
                )
            cleaned.append(trimmed)
        return cleaned


class StartGameRequest(BaseModel):
    """Body for ``POST /api/games``."""

    setting: str = Field(min_length=1, max_length=_SETTING_MAX_CHARS)
    language: str = _DEFAULT_LANGUAGE
    character: CharacterCreationInput | None = None


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
    rendered through ``formatting.markdown_render.to_html`` and — when the
    entity collector ran for this turn — already carries the inline
    ``<span class="poi" data-kind=... data-id=...>`` wrappers.
    """

    role: Literal["player", "narrator"]
    text: str
    html: str


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
    ``narration_html`` is the same value pre-rendered for browser clients
    with inline entity spans already baked in.
    """

    narration: str
    narration_html: str
    turn_count: int
    character: CharacterInfo
