"""Pydantic request/response models for the web API.

This is the contract that any client (web, PWA, native mobile) consumes,
so keep it small, stable, and free of implementation details. Helpers that
build/serialize values live in ``transcript.py``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from interfaces.web.character_schemas import CharacterInfo
from interfaces.web.world_schemas import WorldView

# Allowed (intent, entity_kind) pairs for a structured player gesture. A
# tap can only ever mean one verb per target kind, so the matrix is fixed
# here rather than inferred per request.
_ALLOWED_GESTURE_PAIRS: frozenset[tuple[str, str]] = frozenset(
    (
        *((intent, "npc") for intent in ("examine", "talk", "attack", "steal")),
        ("examine", "poi"),
        ("examine", "item"),
        ("move", "location"),
    )
)

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


class PlayerGesture(BaseModel):
    """A language-neutral tap on an in-prose entity or a map place.

    The client never composes a phrase — it sends *what was tapped*
    (``entity_kind`` + the opaque ``entity_id`` the server emitted) and
    *what it means* (``intent``). The server resolves the target's
    player-visible name and composes the action in the session language.
    """

    intent: Literal["examine", "talk", "attack", "steal", "move"]
    entity_kind: Literal["npc", "poi", "item", "location"]
    entity_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check_intent_kind(self) -> "PlayerGesture":
        if (self.intent, self.entity_kind) not in _ALLOWED_GESTURE_PAIRS:
            raise ValueError(f"intent '{self.intent}' is not valid for entity_kind '{self.entity_kind}'")
        return self


class ActionRequest(BaseModel):
    """Body for ``POST /api/games/{game_id}/actions``.

    Carries **exactly one** of a free-text ``action`` or a structured
    ``gesture``. The free-text path is unchanged for existing clients.
    """

    action: str | None = Field(default=None, max_length=_ACTION_MAX_CHARS)
    gesture: PlayerGesture | None = None

    @model_validator(mode="after")
    def _check_exactly_one(self) -> "ActionRequest":
        if (self.action is None) == (self.gesture is None):
            raise ValueError("provide exactly one of 'action' or 'gesture'")
        if self.action is not None and not self.action.strip():
            raise ValueError("'action' must not be blank")
        return self


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
    world: WorldView


class ActionResponse(BaseModel):
    """Response body for ``POST /api/games/{game_id}/actions``.

    ``narration`` is the raw markdown text the engine produced;
    ``narration_html`` is the same value pre-rendered for browser clients
    with inline entity spans already baked in. ``action_html`` is the
    HTML-escaped player line the server actually ran — needed for gesture
    turns, where the client never composed the phrase itself; free-text
    clients ignore it because they already echoed the player's input.
    """

    narration: str
    narration_html: str
    action_html: str | None = None
    turn_count: int
    character: CharacterInfo
    world: WorldView
