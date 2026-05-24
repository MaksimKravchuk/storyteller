"""Pydantic models for the web story library API."""

from __future__ import annotations

from pydantic import BaseModel


class GameSummary(BaseModel):
    """Compact library row for one caller-owned story."""

    game_id: str
    title: str
    setting: str
    turn_count: int


class GameListResponse(BaseModel):
    """Response body for ``GET /api/games``."""

    games: list[GameSummary]
