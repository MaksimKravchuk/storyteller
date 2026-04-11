"""Telegram bot command handlers (/start, /quit, language callback)."""

from __future__ import annotations

from typing import Any

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from db.engine import get_db
from db.repository import GameRepository

_SESSION_ID_KEY = "id"
_STATE_IDLE = "idle"

_LANGUAGE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("\U0001f1ec\U0001f1e7 English", "English"),
    ("\U0001f1f7\U0001f1fa Russian", "Russian"),
    ("\U0001f1ea\U0001f1f8 Spanish", "Spanish"),
    ("\U0001f1eb\U0001f1f7 French", "French"),
    ("\U0001f1e9\U0001f1ea German", "German"),
    ("\U0001f1ef\U0001f1f5 Japanese", "Japanese"),
)


def db_factory(context: ContextTypes.DEFAULT_TYPE) -> Any:
    """Return the DB session factory from bot_data."""
    return context.bot_data["db_session_factory"]


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    assert update.effective_chat is not None  # noqa: S101
    assert update.message is not None  # noqa: S101
    async with get_db(db_factory(context)) as db:
        repo = GameRepository(db)
        session = await repo.get_or_create_session(update.effective_chat.id)
        await repo.update_session(session[_SESSION_ID_KEY], state="awaiting_language")

    await update.message.reply_text(
        "Welcome to Storyteller!\n\nChoose your story language:",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton(label, callback_data=f"lang:{code}")] for label, code in _LANGUAGE_OPTIONS],
        ),
    )


async def handle_language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle language selection callback."""
    query = update.callback_query
    assert query is not None  # noqa: S101
    assert query.data is not None  # noqa: S101
    assert update.effective_chat is not None  # noqa: S101
    await query.answer()
    language = query.data.split(":", 1)[1]

    async with get_db(db_factory(context)) as db:
        repo = GameRepository(db)
        session = await repo.get_or_create_session(update.effective_chat.id)
        if session["state"] != "awaiting_language":
            return
        await repo.update_session(session[_SESSION_ID_KEY], state="awaiting_setting", language=language)

    await query.edit_message_text(
        f"Language set to {language}.\n\nDescribe your desired setting (e.g. 'Rome, 1st century AD'):"
    )


async def cmd_quit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /quit command."""
    assert update.effective_chat is not None  # noqa: S101
    assert update.message is not None  # noqa: S101
    chat_id = update.effective_chat.id
    async with get_db(db_factory(context)) as db:
        repo = GameRepository(db)
        session = await repo.get_or_create_session(chat_id)
        await repo.update_session(session[_SESSION_ID_KEY], state=_STATE_IDLE)
    await update.message.reply_text("Game ended. Send /start to play again.")


async def _handle_wait_action(update: Update, context: ContextTypes.DEFAULT_TYPE, repo: Any, session: dict) -> None:
    """Process a /wait action through the game engine."""
    from interfaces.telegram_handlers import handle_playing
    from interfaces.telegram_bot import MessageContext

    ctx = MessageContext(
        update=update,
        repo=repo,
        session_id=session[_SESSION_ID_KEY],
        text="/wait",
        cfg=context.bot_data["cfg"],
        language=session.get("language", "English"),
    )
    await handle_playing(ctx)


async def cmd_wait(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /wait command — player skips their turn."""
    assert update.effective_chat is not None  # noqa: S101
    assert update.message is not None  # noqa: S101
    async with get_db(db_factory(context)) as db:
        repo = GameRepository(db)
        session = await repo.get_or_create_session(update.effective_chat.id)
        if session["state"] != "playing":
            await update.message.reply_text("No active game. Send /start to begin.")
            return
        await _handle_wait_action(update, context, repo, session)
