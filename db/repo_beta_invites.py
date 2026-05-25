"""Admin beta invite persistence helpers."""

from __future__ import annotations

from typing import Any

from sqlalchemy import Select, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.tables import beta_invites

_INVITED_STATUS = "invited"
_ACCEPTED_STATUS = "accepted"


class BetaInviteStore:
    """Persistence operations for admin-managed beta invites."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert_invite(self, email: str, invited_by: str | None = None) -> dict[str, Any]:
        """Create or re-enable a beta invite for a normalized email address."""
        normalized = _normalize_email(email)
        existing = await self._get_invite(normalized)
        if existing:
            if existing["status"] == _ACCEPTED_STATUS:
                return existing
            return await self._reinvite(normalized, invited_by)
        return await self._create_invite(normalized, invited_by)

    async def list_invites(self) -> list[dict[str, Any]]:
        """Return beta invites newest first for admin management."""
        stmt = select(beta_invites).order_by(*_invite_ordering())
        rows = await self._session.execute(stmt)
        return [dict(row) for row in rows.mappings()]

    async def _get_invite(self, email: str) -> dict[str, Any] | None:
        rows = await self._session.execute(_invite_by_email_stmt(email))
        row = rows.mappings().first()
        if row is not None:
            return dict(row)
        return None

    async def _create_invite(self, email: str, invited_by: str | None) -> dict[str, Any]:
        rows = await self._session.execute(_create_invite_stmt(email, invited_by))
        return dict(rows.mappings().one())

    async def _reinvite(self, email: str, invited_by: str | None) -> dict[str, Any]:
        stmt = (
            update(beta_invites)
            .where(beta_invites.c.email == email)
            .values(**_invite_update_values(invited_by))
            .returning(beta_invites)
        )
        rows = await self._session.execute(stmt)
        return dict(rows.mappings().one())


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _invite_by_email_stmt(email: str) -> Select:
    return select(beta_invites).where(beta_invites.c.email == email)


def _create_invite_stmt(email: str, invited_by: str | None) -> Any:
    return insert(beta_invites).values(**_invite_insert_values(email, invited_by)).returning(beta_invites)


def _invite_ordering() -> tuple[Any, Any]:
    return beta_invites.c.invited_at.desc(), beta_invites.c.created_at.desc()


def _invite_insert_values(email: str, invited_by: str | None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "email": email,
        "status": _INVITED_STATUS,
        "accepted_at": None,
        "invited_at": func.clock_timestamp(),
    }
    if invited_by is not None:
        payload["invited_by"] = invited_by
    return payload


def _invite_update_values(invited_by: str | None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": _INVITED_STATUS,
        "accepted_at": None,
        "invited_at": func.clock_timestamp(),
    }
    if invited_by is not None:
        payload["invited_by"] = invited_by
    return payload
