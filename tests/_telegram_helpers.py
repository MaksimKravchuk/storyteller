"""Minimal MagicMock-based Telegram Update / Context builders for unit tests.

This module is intentionally prefixed with an underscore so pytest does not
collect it as a test module. It is imported explicitly by individual
``tests/test_telegram_*.py`` files to produce lightweight stand-ins for
``telegram.Update`` / ``telegram.ext.Context`` objects without pulling in the
real python-telegram-bot machinery.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

_DEFAULT_CHAT_ID = 42


def make_text_update(chat_id: int = _DEFAULT_CHAT_ID, text: str = "hello") -> Any:
    """Build a MagicMock shaped like ``telegram.Update`` for a text message."""
    update = MagicMock()
    update.effective_chat.id = chat_id
    update.message.text = text
    update.message.reply_text = AsyncMock()
    update.callback_query = None
    return update


def make_callback_update(chat_id: int = _DEFAULT_CHAT_ID, callback_data: str = "lang:English") -> Any:
    """Build a MagicMock shaped like ``telegram.Update`` for a callback query."""
    update = MagicMock()
    update.effective_chat.id = chat_id
    update.callback_query.data = callback_data
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    return update


def make_context(cfg: Any = None, db_factory: Any = None) -> Any:
    """Build a MagicMock shaped like a PTB ``ContextTypes.DEFAULT_TYPE``."""
    ctx = MagicMock()
    ctx.bot_data = {"cfg": cfg, "db_session_factory": db_factory}
    return ctx
