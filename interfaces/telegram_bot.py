"""Telegram bot interface for Storyteller — DB-backed sessions."""

from __future__ import annotations

from loguru import logger

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import Config
from db.engine import get_db
from db.repository import GameRepository
from engine.factory import create_engine, create_engine_from_state
from engine.game_engine import GameEngine
from llm.call_logger import current_session_id, get_and_clear_buffer, reset_buffer

_SESSION_ID_KEY = "id"
_STATE_IDLE = "idle"


async def _persist_engine_state(
    repo: GameRepository,
    session_id: str,
    engine: GameEngine,
    turn_number: int | None,
) -> None:
    """Save game state and flush any buffered AI call logs."""
    game_state = engine.game_state
    if game_state is None:
        raise RuntimeError("engine.game_state is None after act — engine did not initialise correctly")
    if engine.knowledge_graph is None:
        raise RuntimeError("engine.knowledge_graph is None after act — engine did not initialise correctly")
    await repo.save_game_state(
        session_id,
        game_state,
        engine.knowledge_graph,
        engine.event_manager.all_events if engine.event_manager else [],
    )
    ai_logs = get_and_clear_buffer()
    if ai_logs:
        await repo.save_ai_call_logs(ai_logs, turn_number=turn_number)


_LANGUAGE_OPTIONS: tuple[tuple[str, str], ...] = (
    ("\U0001f1ec\U0001f1e7 English", "English"),
    ("\U0001f1f7\U0001f1fa Russian", "Russian"),
    ("\U0001f1ea\U0001f1f8 Spanish", "Spanish"),
    ("\U0001f1eb\U0001f1f7 French", "French"),
    ("\U0001f1e9\U0001f1ea German", "German"),
    ("\U0001f1ef\U0001f1f5 Japanese", "Japanese"),
)


def _db_factory(context: ContextTypes.DEFAULT_TYPE):
    return context.bot_data["db_session_factory"]


def _cfg(context: ContextTypes.DEFAULT_TYPE) -> Config:
    return context.bot_data["cfg"]


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    async with get_db(_db_factory(context)) as db:
        repo = GameRepository(db)
        session = await repo.get_or_create_session(chat_id)
        await repo.update_session(session[_SESSION_ID_KEY], state="awaiting_language")

    keyboard = [
        [InlineKeyboardButton(label, callback_data=f"lang:{lang_code}")] for label, lang_code in _LANGUAGE_OPTIONS
    ]
    await update.message.reply_text(
        "Welcome to Storyteller!\n\nChoose your story language:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def handle_language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    chat_id = update.effective_chat.id
    language = query.data.split(":", 1)[1]

    async with get_db(_db_factory(context)) as db:
        repo = GameRepository(db)
        session = await repo.get_or_create_session(chat_id)
        if session["state"] != "awaiting_language":
            return
        await repo.update_session(session[_SESSION_ID_KEY], state="awaiting_setting", language=language)

    await query.edit_message_text(
        f"Language set to {language}.\n\nDescribe your desired setting (e.g. 'Rome, 1st century AD'):"
    )


async def cmd_quit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    async with get_db(_db_factory(context)) as db:
        repo = GameRepository(db)
        session = await repo.get_or_create_session(chat_id)
        await repo.update_session(session[_SESSION_ID_KEY], state=_STATE_IDLE)
    await update.message.reply_text("Game ended. Send /start to play again.")


async def _start_new_game(engine, repo, session_id, update, text) -> None:
    """Run start_game and persist. Extracted to keep try-body short."""
    opening = await engine.start_game(text)
    await _persist_engine_state(repo, session_id, engine, turn_number=None)
    await repo.update_session(session_id, state="playing")
    await update.message.reply_text(opening)


async def _process_player_action(engine, repo, session_id, update, text) -> None:
    """Run process_action and persist. Extracted to keep try-body short."""
    response = await engine.process_action(text)
    turn_number = engine.game_state.turn_count if engine.game_state else None
    await _persist_engine_state(repo, session_id, engine, turn_number=turn_number)
    await update.message.reply_text(response)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    text = update.message.text.strip()
    cfg = _cfg(context)

    async with get_db(_db_factory(context)) as db:
        repo = GameRepository(db)
        session = await repo.get_or_create_session(chat_id)
        state = session["state"]
        session_id = session[_SESSION_ID_KEY]
        language = session["language"]

        if state == _STATE_IDLE:
            await update.message.reply_text("Send /start to begin a new game.")
            return

        if state == "awaiting_setting":
            await update.message.reply_text(
                "Researching setting and generating opening scene... (this may take a minute)"
            )
            with logger.contextualize(session_id=session_id):
                current_session_id.set(session_id)
                reset_buffer()
                engine = create_engine(cfg, language=language)
                try:
                    await _start_new_game(engine, repo, session_id, update, text)
                except Exception:
                    logger.exception("Failed to start game for chat {}", chat_id)
                    await update.message.reply_text("Something went wrong. Try /start again.")
                    await repo.update_session(session_id, state=_STATE_IDLE)
            return

        # PLAYING state
        loaded = await repo.load_game_state(session_id)
        if loaded is None:
            await update.message.reply_text("No game found. Send /start to begin.")
            await repo.update_session(session_id, state=_STATE_IDLE)
            return

        game_state, kg, events = loaded
        engine = await create_engine_from_state(cfg, game_state, kg, events, language=language)

        with logger.contextualize(session_id=session_id):
            current_session_id.set(session_id)
            reset_buffer()
            try:
                await _process_player_action(engine, repo, session_id, update, text)
            except Exception:
                logger.exception("Error processing action for chat {}", chat_id)
                await update.message.reply_text("Something went wrong processing your action. Try again.")


def build_bot(cfg: Config, db_session_factory) -> Application:
    """Build and configure the Telegram bot Application (does not start it)."""
    if not cfg.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN not set in environment / .env")

    app = Application.builder().token(cfg.telegram_bot_token).build()

    # Store shared state in bot_data
    app.bot_data["cfg"] = cfg
    app.bot_data["db_session_factory"] = db_session_factory

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("quit", cmd_quit))
    app.add_handler(CallbackQueryHandler(handle_language_callback, pattern=r"^lang:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    return app
