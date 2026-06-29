"""Account and beta invite persistence helpers."""

from __future__ import annotations

from typing import Any, Mapping, cast

from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.tables import accounts, beta_invites
from defaults.entitlements import DEFAULT_USER_PLAN

_INVITED_STATUS = "invited"
_ACCEPTED_STATUS = "accepted"
_REVOKED_STATUS = "revoked"


class AccountStore:
    """Persistence operations for Supabase-authenticated beta accounts."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_invite_by_email(self, email: str) -> Mapping[str, Any] | None:
        """Return a beta invite by normalized email, if present."""
        normalized = normalize_email(email)
        invite_stmt = select(beta_invites).where(beta_invites.c.email == normalized)
        invite_rows = await self._session.execute(invite_stmt)
        return cast("Mapping[str, Any] | None", invite_rows.mappings().first())

    async def create_invite(self, email: str, invited_by: str | None = None) -> Mapping[str, Any]:
        """Create an invite for a normalized email address."""
        invite_values = {"email": normalize_email(email)}
        if invited_by is not None:
            invite_values["invited_by"] = invited_by
        create_stmt = insert(beta_invites).values(**invite_values).returning(beta_invites)
        invite_rows = await self._session.execute(create_stmt)
        return cast("Mapping[str, Any]", invite_rows.mappings().one())

    async def get_by_supabase_user_id(self, supabase_user_id: str) -> Mapping[str, Any] | None:
        """Return an account by Supabase user id, if present."""
        account_stmt = select(accounts).where(accounts.c.supabase_user_id == str(supabase_user_id))
        account_rows = await self._session.execute(account_stmt)
        return cast("Mapping[str, Any] | None", account_rows.mappings().first())

    async def get_or_create_for_invited_user(self, supabase_user_id: str, email: str) -> Mapping[str, Any]:
        """Return an existing account or create one for an invited Supabase user."""
        existing = await self.get_by_supabase_user_id(supabase_user_id)
        if existing is not None:
            return existing
        normalized = normalize_email(email)
        create_stmt = (
            insert(accounts)
            .values(
                supabase_user_id=str(supabase_user_id),
                email=normalized,
                plan=DEFAULT_USER_PLAN,
            )
            .returning(accounts)
        )
        account_rows = await self._session.execute(create_stmt)
        await self._mark_invite_accepted(normalized)
        return cast("Mapping[str, Any]", account_rows.mappings().one())

    async def is_email_invited(self, email: str) -> bool:
        """Return True when the normalized email has a non-revoked invite."""
        invite = await self.get_invite_by_email(email)
        if invite is None:
            return False
        return invite["status"] in {_INVITED_STATUS, _ACCEPTED_STATUS} and invite["status"] != _REVOKED_STATUS

    async def _mark_invite_accepted(self, email: str) -> None:
        await self._session.execute(
            update(beta_invites)
            .where(beta_invites.c.email == email)
            .where(beta_invites.c.status == _INVITED_STATUS)
            .values(status=_ACCEPTED_STATUS, accepted_at=func.now()),
        )


def normalize_email(email: str) -> str:
    """Normalize email addresses for invite lookups."""
    return email.strip().lower()
