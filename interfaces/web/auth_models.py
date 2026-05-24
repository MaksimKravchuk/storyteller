"""Small data models used by beta authentication helpers."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SupabaseClaims:
    """Minimal verified claims needed by the beta gate."""

    sub: str
    email: str


@dataclass(frozen=True)
class AuthenticatedUser:
    """Local account metadata for an authenticated beta user."""

    account_id: str
    supabase_user_id: str
    email: str
    plan: str
    is_admin: bool


@dataclass(frozen=True)
class PlayerFeedbackContext:
    """Player identity attached to beta feedback submissions."""

    player_id: str
    email: str | None
