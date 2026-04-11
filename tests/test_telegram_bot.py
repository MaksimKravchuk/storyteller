"""Tests for interfaces.telegram_bot — build_bot wiring and handle_message router."""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import allure
import pytest

from config import Config
from tests._telegram_helpers import make_context, make_text_update

pytest.importorskip("telegram")

from interfaces import telegram_bot  # noqa: E402

pytestmark = [
    allure.epic("Player Interfaces"),
    allure.feature("Telegram bot"),
]


@asynccontextmanager
async def _fake_db_cm(*_args, **_kwargs):
    """Async context manager that yields a MagicMock DB session."""
    yield MagicMock()


def _patch_db_and_repo(session: dict):
    """Patch ``get_db`` / ``GameRepository`` inside telegram_bot; return patchers and repo."""
    repo = AsyncMock()
    repo.get_or_create_session = AsyncMock(return_value=session)
    db_patch = patch("interfaces.telegram_bot.get_db", _fake_db_cm)
    repo_patch = patch("interfaces.telegram_bot.GameRepository", return_value=repo)
    return db_patch, repo_patch, repo


def _reply_message(update) -> str:
    """Extract the first positional arg of the most recent reply_text call."""
    reply_mock = update.message.reply_text
    return reply_mock.call_args.args[0]


@allure.story("build_bot configuration")
@allure.title("build_bot raises RuntimeError when telegram_bot_token is not configured")
def test_build_bot_missing_token() -> None:
    cfg = Config(telegram_bot_token=None)
    with pytest.raises(RuntimeError, match="TELEGRAM_BOT_TOKEN"):
        telegram_bot.build_bot(cfg, db_session_factory=MagicMock())


@allure.story("build_bot configuration")
@allure.title("build_bot stores cfg and db_session_factory inside Application.bot_data")
def test_build_bot_stores_config() -> None:
    cfg = Config(telegram_bot_token="TKN")
    factory = MagicMock()
    fake_app = MagicMock()
    fake_app.bot_data = {}
    builder_chain = MagicMock()
    builder_chain.token.return_value.build.return_value = fake_app

    with patch("interfaces.telegram_bot.Application.builder", return_value=builder_chain):
        result = telegram_bot.build_bot(cfg, factory)
        assert result is fake_app
        assert fake_app.bot_data["cfg"] is cfg
        assert fake_app.bot_data["db_session_factory"] is factory


@allure.story("build_bot configuration")
@allure.title("build_bot registers command, callback and message handlers on the Application")
def test_build_bot_registers_handlers() -> None:
    cfg = Config(telegram_bot_token="TKN")
    fake_app = MagicMock()
    fake_app.bot_data = {}
    builder_chain = MagicMock()
    builder_chain.token.return_value.build.return_value = fake_app

    with patch("interfaces.telegram_bot.Application.builder", return_value=builder_chain):
        telegram_bot.build_bot(cfg, MagicMock())
        handler_count = 5
        assert fake_app.add_handler.call_count == handler_count
        handler_types = [type(call.args[0]).__name__ for call in fake_app.add_handler.call_args_list]
        assert handler_types.count("CommandHandler") == 3
        assert "CallbackQueryHandler" in handler_types
        assert "MessageHandler" in handler_types


@allure.story("handle_message state routing")
@allure.title("handle_message in idle state replies with the /start prompt")
@pytest.mark.asyncio
async def test_handle_message_idle_replies_start_prompt() -> None:
    update = make_text_update(text="anything")
    context = make_context(cfg=SimpleNamespace(telegram_bot_token="TKN"))

    db_patch, repo_patch, _repo = _patch_db_and_repo(
        {"id": "s1", "state": "idle", "language": "English"},
    )
    with db_patch, repo_patch:
        await telegram_bot.handle_message(update, context)

    update.message.reply_text.assert_awaited_once()
    assert "/start" in _reply_message(update)


@allure.story("handle_message state routing")
@allure.title("handle_message with awaiting_setting state routes to handlers.handle_awaiting_setting")
@pytest.mark.asyncio
async def test_handle_message_awaiting_setting_routes_to_handlers() -> None:
    update = make_text_update(text="Rome")
    context = make_context(cfg=SimpleNamespace(telegram_bot_token="TKN"))

    db_patch, repo_patch, _repo = _patch_db_and_repo(
        {"id": "s2", "state": "awaiting_setting", "language": "English"},
    )
    awaiting_mock = AsyncMock()
    playing_mock = AsyncMock()
    with (
        db_patch,
        repo_patch,
        patch(
            "interfaces.telegram_bot.handlers.handle_awaiting_setting",
            new=awaiting_mock,
        ),
        patch(
            "interfaces.telegram_bot.handlers.handle_playing",
            new=playing_mock,
        ),
    ):
        await telegram_bot.handle_message(update, context)

    awaiting_mock.assert_awaited_once()
    playing_mock.assert_not_awaited()
    ctx_arg = awaiting_mock.call_args.args[0]
    assert ctx_arg.session_id == "s2"
    assert ctx_arg.text == "Rome"
    assert ctx_arg.language == "English"


@allure.story("handle_message state routing")
@allure.title("handle_message with playing state routes to handlers.handle_playing")
@pytest.mark.asyncio
async def test_handle_message_playing_routes_to_handlers() -> None:
    update = make_text_update(text="look around")
    context = make_context(cfg=SimpleNamespace(telegram_bot_token="TKN"))

    db_patch, repo_patch, _repo = _patch_db_and_repo(
        {"id": "s3", "state": "playing", "language": "English"},
    )
    playing_mock = AsyncMock()
    awaiting_mock = AsyncMock()
    with (
        db_patch,
        repo_patch,
        patch(
            "interfaces.telegram_bot.handlers.handle_playing",
            new=playing_mock,
        ),
        patch(
            "interfaces.telegram_bot.handlers.handle_awaiting_setting",
            new=awaiting_mock,
        ),
    ):
        await telegram_bot.handle_message(update, context)

    playing_mock.assert_awaited_once()
    awaiting_mock.assert_not_awaited()
    ctx_arg = playing_mock.call_args.args[0]
    assert ctx_arg.session_id == "s3"
    assert ctx_arg.text == "look around"
