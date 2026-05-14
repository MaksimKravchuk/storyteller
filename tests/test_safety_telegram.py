"""HTTP-equivalent test for the Telegram surface: a flagged inbound action
must produce a refusal reply rather than a generic "something went wrong"
message — and the persistence step must be skipped on rejection.

This closes the consumer-side seam called out by CLAUDE.md: the engine
raises :class:`SafetyRejectedError`, and the Telegram handler is what
turns that into a user-facing reply.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import allure
import pytest

from interfaces.telegram_handlers import process_player_action
from safety.moderator import SafetyRejectedError
from safety.result import (
    ModerationCategory,
    ModerationResult,
    ModerationSeverity,
)

pytestmark = [
    allure.epic("Engine & LLM Infrastructure"),
    allure.feature("Content safety"),
]


def _flagged_result() -> ModerationResult:
    return ModerationResult(
        flagged=True,
        severities={ModerationCategory.HATE: ModerationSeverity.HIGH},
        triggering_categories=(ModerationCategory.HATE,),
    )


def _build_update() -> MagicMock:
    """Build a Telegram-update double whose ``reply_text`` is an async mock."""
    update = MagicMock()
    update.message = MagicMock()
    update.message.reply_text = AsyncMock()
    return update


@allure.story("Telegram refusal")
@allure.title("process_player_action replies with the refusal text when the engine flags the input")
@pytest.mark.asyncio
async def test_telegram_refusal_reaches_user() -> None:
    refusal_text = "I can't process that — content policy violation."
    engine = MagicMock()
    engine.process_action = AsyncMock(side_effect=SafetyRejectedError(refusal_text, _flagged_result()))
    repo = AsyncMock()
    update = _build_update()

    await process_player_action(engine, repo, "sess-1", update, "harmful input")

    update.message.reply_text.assert_awaited_once_with(refusal_text)


@allure.story("Telegram refusal")
@allure.title("process_player_action skips persistence entirely when the engine flags the input")
@pytest.mark.asyncio
async def test_telegram_refusal_skips_persistence() -> None:
    engine = MagicMock()
    engine.process_action = AsyncMock(side_effect=SafetyRejectedError("nope", _flagged_result()))
    repo = AsyncMock()
    update = _build_update()

    await process_player_action(engine, repo, "sess-1", update, "harmful input")

    # Whole-repo assertion catches every persistence call, not just a
    # hand-picked subset — a bare ``AsyncMock`` records every attribute
    # access, so any future write method would show up in ``mock_calls``.
    assert repo.mock_calls == [], "persistence ran despite a flagged input: {0}".format(repo.mock_calls)
