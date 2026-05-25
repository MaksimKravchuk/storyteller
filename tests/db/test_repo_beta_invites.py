"""Tests for admin beta invite persistence helpers."""

from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timezone

import allure
import pytest
from sqlalchemy import func, insert
from sqlalchemy.ext.asyncio import AsyncSession

from db import tables as tbl
from db.repo_beta_invites import BetaInviteStore

pytestmark = pytest.mark.db


async def _create_account(async_session: AsyncSession, email: str, created_at=None) -> dict:
    values: dict = {"supabase_user_id": str(_uuid.uuid4()), "email": email}
    if created_at is not None:
        values["created_at"] = created_at
    rows = await async_session.execute(insert(tbl.accounts).values(**values).returning(tbl.accounts))
    return dict(rows.mappings().one())


@allure.epic("Memory & Persistence")
@allure.feature("Beta invites")
class TestBetaInvites:
    @allure.story("Invite management")
    @allure.title("upsert_invite normalizes and creates a beta invite")
    @pytest.mark.asyncio
    async def test_upsert_invite_normalizes_and_creates_invite(self, async_session: AsyncSession) -> None:
        invite = await BetaInviteStore(async_session).upsert_invite(" Tester@Example.COM ")

        assert invite["email"] == "tester@example.com"
        assert invite["status"] == "invited"
        assert invite["accepted_at"] is None

    @allure.story("Invite management")
    @allure.title("upsert_invite re-enables an existing revoked invite")
    @pytest.mark.asyncio
    async def test_upsert_invite_reenables_existing_invite(self, async_session: AsyncSession) -> None:
        await async_session.execute(
            insert(tbl.beta_invites).values(email="tester@example.com", status="revoked"),
        )

        invite = await BetaInviteStore(async_session).upsert_invite("tester@example.com")

        assert invite["email"] == "tester@example.com"
        assert invite["status"] == "invited"
        assert invite["accepted_at"] is None

    @allure.story("Invite management")
    @allure.title("upsert_invite preserves an already accepted invite")
    @pytest.mark.asyncio
    async def test_upsert_invite_preserves_accepted_invite(self, async_session: AsyncSession) -> None:
        await async_session.execute(
            insert(tbl.beta_invites).values(
                email="tester@example.com",
                status="accepted",
                accepted_at=func.now(),
            ),
        )

        invite = await BetaInviteStore(async_session).upsert_invite("tester@example.com")

        assert invite["email"] == "tester@example.com"
        assert invite["status"] == "accepted"
        assert invite["accepted_at"] is not None

    @allure.story("Invite management")
    @allure.title("list_invites returns beta invites newest first")
    @pytest.mark.asyncio
    async def test_list_invites_returns_newest_first(self, async_session: AsyncSession) -> None:
        await async_session.execute(
            insert(tbl.beta_invites).values(email="old@example.com", status="invited"),
        )
        store = BetaInviteStore(async_session)
        await store.upsert_invite("new@example.com")

        invites = await store.list_invites()

        assert [invite["email"] for invite in invites[:2]] == ["new@example.com", "old@example.com"]

    @allure.story("Invite management")
    @allure.title("list_invites attaches account_id when an account with that email exists")
    @pytest.mark.asyncio
    async def test_list_invites_includes_account_id_when_email_matches(self, async_session: AsyncSession) -> None:
        account = await _create_account(async_session, "tester@example.com")
        store = BetaInviteStore(async_session)
        await store.upsert_invite("tester@example.com")

        invites = await store.list_invites()
        match = next(invite for invite in invites if invite["email"] == "tester@example.com")
        assert str(match["account_id"]) == str(account["id"])

    @allure.story("Invite management")
    @allure.title("list_invites returns null account_id when no account exists for the invite email")
    @pytest.mark.asyncio
    async def test_list_invites_account_id_null_when_no_account(self, async_session: AsyncSession) -> None:
        store = BetaInviteStore(async_session)
        await store.upsert_invite("orphan@example.com")

        invites = await store.list_invites()
        match = next(invite for invite in invites if invite["email"] == "orphan@example.com")
        assert match["account_id"] is None

    @allure.story("Invite management")
    @allure.title("list_invites resolves email collisions deterministically to the most-recent account")
    @pytest.mark.asyncio
    async def test_list_invites_resolves_email_collision_to_most_recent_account(
        self,
        async_session: AsyncSession,
    ) -> None:
        # accounts.email is non-unique by schema; pick the newest deterministically.
        # Explicit created_at avoids same-transaction func.now() ambiguity.
        older_ts = datetime(2025, 1, 1, tzinfo=timezone.utc)
        newer_ts = datetime(2025, 6, 1, tzinfo=timezone.utc)
        await _create_account(async_session, "dup@example.com", created_at=older_ts)
        newer = await _create_account(async_session, "dup@example.com", created_at=newer_ts)
        store = BetaInviteStore(async_session)
        await store.upsert_invite("dup@example.com")

        first_call = await store.list_invites()
        second_call = await store.list_invites()
        match_first = next(invite for invite in first_call if invite["email"] == "dup@example.com")
        match_second = next(invite for invite in second_call if invite["email"] == "dup@example.com")
        assert str(match_first["account_id"]) == str(newer["id"])
        # Determinism: repeated calls must return the same winner.
        assert match_first["account_id"] == match_second["account_id"]

    @allure.story("Invite management")
    @allure.title("list_invites JOIN resolves through case-folding for legacy mixed-case account emails")
    @pytest.mark.asyncio
    async def test_list_invites_join_handles_mixed_case_account_email(self, async_session: AsyncSession) -> None:
        # Insert account email raw (bypass normalize_email) to simulate legacy mixed-case rows.
        await async_session.execute(
            insert(tbl.accounts).values(supabase_user_id=str(_uuid.uuid4()), email="MiXeD@Example.COM"),
        )
        store = BetaInviteStore(async_session)
        # upsert_invite lowercases the invite side; the JOIN must lowercase the account side too.
        await store.upsert_invite("mixed@example.com")

        invites = await store.list_invites()
        match = next(invite for invite in invites if invite["email"] == "mixed@example.com")
        assert match["account_id"] is not None
