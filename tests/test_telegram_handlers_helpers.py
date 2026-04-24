"""Tests for interfaces.telegram_handlers_helpers.recover_from_start_failure."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import allure
import pytest

from interfaces.telegram_handlers_helpers import recover_from_start_failure

pytestmark = [
    allure.epic("Player Interfaces"),
    allure.feature("Telegram handlers"),
]


@pytest.mark.asyncio
@allure.story("recover_from_start_failure")
@allure.title("recover_from_start_failure rolls back, notifies the user, and returns the session to idle")
async def test_recover_runs_the_full_sequence() -> None:
    repo = AsyncMock()
    update = SimpleNamespace(message=AsyncMock())
    ctx = SimpleNamespace(repo=repo, update=update, session_id="sess-123")

    await recover_from_start_failure(ctx, chat_id=9999)

    repo.rollback.assert_awaited_once_with()
    update.message.reply_text.assert_awaited_once()
    repo.sessions.update.assert_awaited_once_with("sess-123", state="idle")
