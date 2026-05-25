"""Tests for admin beta invite persistence helpers."""

from __future__ import annotations

import allure
import pytest
from sqlalchemy import func, insert
from sqlalchemy.ext.asyncio import AsyncSession

from db import tables as tbl
from db.repo_beta_invites import BetaInviteStore

pytestmark = pytest.mark.db


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
