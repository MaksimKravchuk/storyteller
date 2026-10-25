"""DB test for the account-level 18+ switch (column default + AccountStore.set_mature_content)."""

from __future__ import annotations

import allure
import pytest

from tests.db.conftest import GameRepository

pytestmark = pytest.mark.db


@allure.epic("Memory & Persistence")
@allure.feature("Accounts")
@allure.story("Mature content")
@allure.title("New accounts start with mature content off; set_mature_content flips it both ways")
@pytest.mark.asyncio
async def test_set_mature_content_round_trip(repo: GameRepository) -> None:
    account = await repo.accounts.get_or_create_for_invited_user("supabase-user-1", "adult@example.com")
    assert account["mature_content"] is False

    await repo.accounts.set_mature_content(str(account["id"]), True)
    stored = await repo.accounts.get_by_supabase_user_id("supabase-user-1")
    assert stored is not None
    assert stored["mature_content"] is True

    await repo.accounts.set_mature_content(str(account["id"]), False)
    stored = await repo.accounts.get_by_supabase_user_id("supabase-user-1")
    assert stored is not None
    assert stored["mature_content"] is False
