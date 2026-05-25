"""Tests for beta feedback persistence — account JOIN + legacy email preservation."""

from __future__ import annotations

import uuid as _uuid

import allure
import pytest
import pytest_asyncio
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from db import tables as tbl
from tests.db.conftest import GameRepository

pytestmark = pytest.mark.db


async def _create_account(async_session: AsyncSession, email: str) -> dict:
    rows = await async_session.execute(
        insert(tbl.accounts).values(supabase_user_id=str(_uuid.uuid4()), email=email).returning(tbl.accounts),
    )
    return dict(rows.mappings().one())


async def _game_id_for_session(async_session: AsyncSession, session_id: str) -> str:
    result = await async_session.execute(
        select(tbl.game_states.c.id).where(tbl.game_states.c.session_id == session_id),
    )
    return str(result.scalar_one())


@pytest_asyncio.fixture
async def feedback_setup(repo: GameRepository, async_session, populated_game_state):
    """Seed an account, a saved game, and return (account, game_id) for feedback tests."""
    account = await _create_account(async_session, "current@example.com")
    session_row = await repo.sessions.create_web(str(account["id"]))
    game_state, kg, events = populated_game_state
    await repo.save_game_state(session_row["id"], game_state, kg, events)
    game_id = await _game_id_for_session(async_session, session_row["id"])
    return account, game_id


@allure.epic("Memory & Persistence")
@allure.feature("Beta feedback")
class TestFeedbackJoin:
    @allure.story("Feedback list")
    @allure.title("list_recent surfaces the live account email via LEFT JOIN on user_id")
    @pytest.mark.asyncio
    async def test_list_recent_joins_account_email(self, repo: GameRepository, feedback_setup) -> None:
        account, game_id = feedback_setup
        await repo.feedback.create(str(account["id"]), "current@example.com", game_id, "bug", "msg")

        rows = await repo.feedback.list_recent()
        match = next(row for row in rows if row["category"] == "bug")
        assert match["account_email"] == "current@example.com"

    @allure.story("Feedback list")
    @allure.title("list_recent returns null account_email when user_id has no matching account")
    @pytest.mark.asyncio
    async def test_list_recent_account_email_null_when_user_id_orphan(
        self,
        repo: GameRepository,
        feedback_setup,
    ) -> None:
        _, game_id = feedback_setup
        orphan_id = str(_uuid.uuid4())
        await repo.feedback.create(orphan_id, "cached@old.example.com", game_id, "bug", "orphan-msg")

        rows = await repo.feedback.list_recent()
        match = next(row for row in rows if row["message"] == "orphan-msg")
        assert match["account_email"] is None
        # Legacy denormalized fallback must still be present for orphan rendering.
        assert match["user_email"] == "cached@old.example.com"

    @allure.story("Feedback list")
    @allure.title("list_recent preserves the legacy user_email alongside account_email when both exist")
    @pytest.mark.asyncio
    async def test_list_recent_preserves_legacy_user_email_alongside_account_email(
        self,
        repo: GameRepository,
        feedback_setup,
    ) -> None:
        # D008 guardrail: live JOIN is canonical; cached user_email stays available for orphan fallback.
        account, game_id = feedback_setup
        await repo.feedback.create(str(account["id"]), "cached@old.example.com", game_id, "bug", "both")

        rows = await repo.feedback.list_recent()
        match = next(row for row in rows if row["message"] == "both")
        assert match["account_email"] == "current@example.com"
        assert match["user_email"] == "cached@old.example.com"
