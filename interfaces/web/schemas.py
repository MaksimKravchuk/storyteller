"""Pydantic request/response models for the web API.

This is the contract that any client (web, PWA, native mobile) consumes,
so keep it small, stable, and free of implementation details.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

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
    """One line in the transcript — either player input or narrator prose."""

    role: Literal["player", "narrator"]
    text: str


class GameSnapshot(BaseModel):
    """The full view a client needs to render the game on load or after start.

    The opening narration is the first narrator entry in ``transcript``.
    """

    game_id: str
    setting: str
    transcript: list[TurnEntry]
    turn_count: int


class ActionResponse(BaseModel):
    """Response body for ``POST /api/games/{game_id}/actions``."""

    narration: str
    turn_count: int


def build_transcript(conversation_log: list[dict]) -> list[TurnEntry]:
    """Convert ``GameState.conversation_log`` entries into flat TurnEntry pairs.

    Each log entry has shape ``{player_action, response, turn, ...}``; we emit
    a player line followed by a narrator line so the client can render a chat
    log without knowing the internal schema.
    """
    transcript: list[TurnEntry] = []
    for entry in conversation_log:
        player_text = entry.get("player_action")
        if player_text:
            transcript.append(TurnEntry(role="player", text=str(player_text)))
        narrator_text = entry.get("response")
        if narrator_text:
            transcript.append(TurnEntry(role="narrator", text=str(narrator_text)))
    return transcript
