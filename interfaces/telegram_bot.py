"""Telegram bot interface for Storyteller — DB-backed sessions."""

from __future__ import annotations

from dataclasses import dataclass

from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from config import Config
from db.engine import get_db
from db.repository import GameRepository
from interfaces import telegram_commands as cmds
from interfaces import telegram_handlers as handlers

_SESSION_ID_KEY = "id"
_STATE_IDLE = "idle"


@dataclass
class MessageContext:
    """Bundles the common parameters passed through message handlers."""

    update: Update
    repo: GameRepository
    session_id: str
    text: str
    cfg: Config
    language: str


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Route incoming text messages to the appropriate state handler."""
    async with get_db(cmds.db_factory(context)) as db:
        repo = GameRepository(db)
        session = await repo.get_or_create_session(update.effective_chat.id)

        if session["state"] == _STATE_IDLE:
            await update.message.reply_text("Send /start to begin a new game.")
            return

        ctx = MessageContext(
            update=update,
            repo=repo,
            session_id=session[_SESSION_ID_KEY],
            text=update.message.text.strip(),
            cfg=context.bot_data["cfg"],
            language=session["language"],
        )

        if session["state"] == "awaiting_setting":
            await handlers.handle_awaiting_setting(ctx, update.effective_chat.id)
            return

        await handlers.handle_playing(ctx)


def build_bot(cfg: Config, db_session_factory) -> Application:
    """Build and configure the Telegram bot Application (does not start it)."""
    if not cfg.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not set in environment / .env")

    app = Application.builder().token(cfg.telegram_bot_token).build()

    app.bot_data["cfg"] = cfg
    app.bot_data["db_session_factory"] = db_session_factory

    app.add_handler(CommandHandler("start", cmds.cmd_start))
    app.add_handler(CommandHandler("quit", cmds.cmd_quit))
    app.add_handler(CallbackQueryHandler(cmds.handle_language_callback, pattern=r"^lang:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    return app
