"""Pydantic request/response models for the mobile HTTP/SSE API.

Wire contract for native clients. Keep this surface small and stable.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

_SETTING_MAX_CHARS = 500
_ACTION_MAX_CHARS = 2000
_DEFAULT_LANGUAGE = "English"


class CreateSessionRequest(BaseModel):
    """Body for ``POST /sessions``."""

    setting: str = Field(min_length=1, max_length=_SETTING_MAX_CHARS)
    language: str = _DEFAULT_LANGUAGE


class ActionRequest(BaseModel):
    """Body for ``POST /sessions/{id}/actions``."""

    action: str = Field(min_length=1, max_length=_ACTION_MAX_CHARS)


class TranscriptEntry(BaseModel):
    """One line in the transcript."""

    role: Literal["player", "narrator"]
    text: str


class CreateSessionResponse(BaseModel):
    """Response body for ``POST /sessions``."""

    session_id: str
    setting: str
    language: str
    opening_scene: str
    turn_count: int
    created_at: datetime


class SessionState(BaseModel):
    """Full session view returned by ``GET /sessions/{id}``."""

    session_id: str
    setting: str
    language: str
    turn_count: int
    scene_description: str
    inventory: list[str]
    recent_transcript: list[TranscriptEntry]
    created_at: datetime


class SessionSummary(BaseModel):
    """Compact session view for the list endpoint."""

    session_id: str
    setting: str
    language: str
    turn_count: int
    created_at: datetime


class SessionListResponse(BaseModel):
    """Response body for ``GET /sessions``."""

    sessions: list[SessionSummary]
