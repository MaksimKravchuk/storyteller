"""Telegram bot interface for Storyteller."""

from __future__ import annotations

import logging
from enum import Enum, auto

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import Config, load_config
from engine.factory import create_engine
from engine.game_engine import GameEngine

logger = logging.getLogger(__name__)


class SessionState(Enum):
    IDLE = auto()
    AWAITING_LANGUAGE = auto()
    AWAITING_SETTING = auto()
    PLAYING = auto()


_LANGUAGE_OPTIONS = [
    ("🇬🇧 English", "English"),
    ("🇷🇺 Russian", "Russian"),
    ("🇪🇸 Spanish", "Spanish"),
    ("🇫🇷 French", "French"),
    ("🇩🇪 German", "German"),
    ("🇯🇵 Japanese", "Japanese"),
]


class UserSession:
    __slots__ = ("state", "engine", "language")

    def __init__(self) -> None:
        self.state = SessionState.IDLE
        self.engine: GameEngine | None = None
        self.language: str = "English"


_sessions: dict[int, UserSession] = {}
_cfg: Config | None = None


def _get_session(chat_id: int) -> UserSession:
    if chat_id not in _sessions:
        _sessions[chat_id] = UserSession()
    return _sessions[chat_id]


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    session = _get_session(update.effective_chat.id)
    session.state = SessionState.AWAITING_LANGUAGE
    session.engine = None

    keyboard = [
        [InlineKeyboardButton(label, callback_data=f"lang:{value}")]
        for label, value in _LANGUAGE_OPTIONS
    ]
    await update.message.reply_text(
        "Welcome to Storyteller!\n\nChoose your story language:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def handle_language_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    await query.answer()

    chat_id = update.effective_chat.id
    session = _get_session(chat_id)

    if session.state != SessionState.AWAITING_LANGUAGE:
        return

    language = query.data.split(":", 1)[1]
    session.language = language
    session.state = SessionState.AWAITING_SETTING

    await query.edit_message_text(
        f"Language set to {language}.\n\n"
        "Describe your desired setting (e.g. 'Rome, 1st century AD'):"
    )


async def cmd_quit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    session = _get_session(update.effective_chat.id)
    session.state = SessionState.IDLE
    session.engine = None
    await update.message.reply_text("Game ended. Send /start to play again.")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    session = _get_session(chat_id)
    text = update.message.text.strip()

    if session.state == SessionState.IDLE:
        await update.message.reply_text("Send /start to begin a new game.")
        return

    if session.state == SessionState.AWAITING_SETTING:
        await update.message.reply_text(
            "Researching setting and generating opening scene... "
            "(this may take a minute)"
        )
        assert _cfg is not None
        engine = create_engine(_cfg, language=session.language)
        try:
            opening = await engine.start_game(text)
        except Exception:
            logger.exception("Failed to start game for chat %s", chat_id)
            await update.message.reply_text(
                "Something went wrong. Try /start again."
            )
            session.state = SessionState.IDLE
            return
        session.engine = engine
        session.state = SessionState.PLAYING
        await update.message.reply_text(opening)
        return

    # PLAYING state
    assert session.engine is not None
    try:
        response = await session.engine.process_action(text)
    except Exception:
        logger.exception("Error processing action for chat %s", chat_id)
        await update.message.reply_text(
            "Something went wrong processing your action. Try again."
        )
        return
    await update.message.reply_text(response)


def run_bot() -> None:
    global _cfg
    _cfg = load_config()

    if not _cfg.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not set in environment / .env")

    app = Application.builder().token(_cfg.telegram_bot_token).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("quit", cmd_quit))
    app.add_handler(CallbackQueryHandler(handle_language_callback, pattern=r"^lang:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Storyteller Telegram bot starting...")
    app.run_polling()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_bot()
