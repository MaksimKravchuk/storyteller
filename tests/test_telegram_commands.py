"""Tests for interfaces.telegram_commands — /start, /quit, /wait, language callback."""

from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import allure
import pytest

from tests._telegram_helpers import make_callback_update, make_context, make_text_update

pytest.importorskip("telegram")

from interfaces import telegram_commands as cmds  # noqa: E402

pytestmark = [
    allure.epic("Player Interfaces"),
    allure.feature("Telegram commands"),
]


@asynccontextmanager
async def _fake_db_cm(*_args, **_kwargs):
    yield MagicMock()


def _patch_db_and_repo(session: dict):
    repo = AsyncMock()
    repo.get_or_create_session = AsyncMock(return_value=session)
    repo.update_session = AsyncMock()
    db_patch = patch("interfaces.telegram_commands.get_db", _fake_db_cm)
    repo_patch = patch("interfaces.telegram_commands.GameRepository", return_value=repo)
    return db_patch, repo_patch, repo


def _reply_text(update) -> str:
    reply_mock = update.message.reply_text
    return reply_mock.call_args.args[0]


def _edit_text(update) -> str:
    edit_mock = update.callback_query.edit_message_text
    return edit_mock.call_args.args[0]


@allure.story("/start command")
@allure.title("cmd_start transitions session to awaiting_language and sends language buttons")
@pytest.mark.asyncio
async def test_cmd_start_sets_awaiting_language() -> None:
    update = make_text_update(text="/start")
    context = make_context(cfg=SimpleNamespace(telegram_bot_token="TKN"))
    db_patch, repo_patch, repo = _patch_db_and_repo(
        {"id": "s1", "state": "idle", "language": "English"},
    )
    with db_patch, repo_patch:
        await cmds.cmd_start(update, context)

    repo.update_session.assert_awaited_once_with("s1", state="awaiting_language")
    update.message.reply_text.assert_awaited_once()
    kwargs = update.message.reply_text.call_args.kwargs
    markup = kwargs["reply_markup"]
    assert hasattr(markup, "inline_keyboard")
    rows = markup.inline_keyboard
    # Six language options configured in _LANGUAGE_OPTIONS.
    languages_expected = 6
    assert len(rows) == languages_expected
    first_button = rows[0][0]
    assert first_button.callback_data.startswith("lang:")


@allure.story("Language callback")
@allure.title("handle_language_callback advances state to awaiting_setting from awaiting_language")
@pytest.mark.asyncio
async def test_handle_language_callback_happy_path() -> None:
    update = make_callback_update(callback_data="lang:Spanish")
    context = make_context(cfg=SimpleNamespace(telegram_bot_token="TKN"))
    db_patch, repo_patch, repo = _patch_db_and_repo(
        {"id": "s1", "state": "awaiting_language", "language": "English"},
    )
    with db_patch, repo_patch:
        await cmds.handle_language_callback(update, context)

    repo.update_session.assert_awaited_once_with(
        "s1",
        state="awaiting_setting",
        language="Spanish",
    )
    update.callback_query.answer.assert_awaited_once()
    update.callback_query.edit_message_text.assert_awaited_once()
    assert "Spanish" in _edit_text(update)


@allure.story("Language callback")
@allure.title("handle_language_callback is a no-op when session is not in awaiting_language state")
@pytest.mark.asyncio
async def test_handle_language_callback_wrong_state() -> None:
    update = make_callback_update(callback_data="lang:French")
    context = make_context(cfg=SimpleNamespace(telegram_bot_token="TKN"))
    db_patch, repo_patch, repo = _patch_db_and_repo(
        {"id": "s1", "state": "playing", "language": "English"},
    )
    with db_patch, repo_patch:
        await cmds.handle_language_callback(update, context)

    repo.update_session.assert_not_awaited()
    update.callback_query.edit_message_text.assert_not_awaited()


@allure.story("/quit command")
@allure.title("cmd_quit resets session state to idle and replies with confirmation")
@pytest.mark.asyncio
async def test_cmd_quit_resets_to_idle() -> None:
    update = make_text_update(text="/quit")
    context = make_context(cfg=SimpleNamespace(telegram_bot_token="TKN"))
    db_patch, repo_patch, repo = _patch_db_and_repo(
        {"id": "s9", "state": "playing", "language": "English"},
    )
    with db_patch, repo_patch:
        await cmds.cmd_quit(update, context)

    repo.update_session.assert_awaited_once_with("s9", state="idle")
    update.message.reply_text.assert_awaited_once()
    assert "/start" in _reply_text(update)


@allure.story("/wait command")
@allure.title("cmd_wait rejects and replies when session is not in playing state")
@pytest.mark.asyncio
async def test_cmd_wait_rejects_when_not_playing() -> None:
    update = make_text_update(text="/wait")
    context = make_context(cfg=SimpleNamespace(telegram_bot_token="TKN"))
    db_patch, repo_patch, _repo = _patch_db_and_repo(
        {"id": "sx", "state": "idle", "language": "English"},
    )
    handle_playing_mock = AsyncMock()
    with (
        db_patch,
        repo_patch,
        patch(
            "interfaces.telegram_handlers.handle_playing",
            new=handle_playing_mock,
        ),
    ):
        await cmds.cmd_wait(update, context)

    handle_playing_mock.assert_not_awaited()
    update.message.reply_text.assert_awaited_once()
    assert "No active game" in _reply_text(update)


@allure.story("/wait command")
@allure.title("cmd_wait in playing state delegates to handle_playing with a /wait MessageContext")
@pytest.mark.asyncio
async def test_cmd_wait_in_playing_delegates_to_handle_playing() -> None:
    update = make_text_update(text="/wait")
    context = make_context(cfg=SimpleNamespace(telegram_bot_token="TKN"))
    db_patch, repo_patch, _repo = _patch_db_and_repo(
        {"id": "sp", "state": "playing", "language": "Russian"},
    )
    handle_playing_mock = AsyncMock()
    with (
        db_patch,
        repo_patch,
        patch(
            "interfaces.telegram_handlers.handle_playing",
            new=handle_playing_mock,
        ),
    ):
        await cmds.cmd_wait(update, context)

    handle_playing_mock.assert_awaited_once()
    ctx_arg = handle_playing_mock.call_args.args[0]
    assert ctx_arg.session_id == "sp"
    assert ctx_arg.text == "/wait"
    assert ctx_arg.language == "Russian"
