"""Telegram message handler logic — extracted from telegram_bot."""

from __future__ import annotations

from typing import Any

from loguru import logger

from db.repository import GameRepository
from engine.factory import create_engine, create_engine_from_state
from engine.game_engine import GameEngine
from formatting.markdown_render import render
from formatting.platform import ClientPlatform
from llm.call_logger import current_session_id, get_and_clear_buffer, reset_buffer

_STATE_IDLE = "idle"
_TELEGRAM_PARSE_MODE = "HTML"


async def persist_engine_state(
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
        await repo.ai_logs.save(ai_logs, turn_number=turn_number)


async def start_new_game(engine: Any, repo: Any, session_id: str, update: Any, text: str) -> None:
    """Run start_game and persist. Extracted to keep try-body short."""
    opening = await engine.start_game(text)
    await persist_engine_state(repo, session_id, engine, turn_number=None)
    await repo.update_session(session_id, state="playing")
    await update.message.reply_text(
        render(opening, ClientPlatform.TELEGRAM_HTML),
        parse_mode=_TELEGRAM_PARSE_MODE,
    )


async def process_player_action(engine: Any, repo: Any, session_id: str, update: Any, text: str) -> None:
    """Run process_action and persist. Extracted to keep try-body short."""
    response = await engine.process_action(text)
    turn_number = engine.game_state.turn_count if engine.game_state else None
    await persist_engine_state(repo, session_id, engine, turn_number=turn_number)
    await update.message.reply_text(
        render(response, ClientPlatform.TELEGRAM_HTML),
        parse_mode=_TELEGRAM_PARSE_MODE,
    )


async def handle_awaiting_setting(ctx: Any, chat_id: int) -> None:
    """Handle the 'awaiting_setting' state: research and start a new game."""
    await ctx.update.message.reply_text(
        "Researching setting and generating opening scene... (this may take a minute)",
    )
    with logger.contextualize(session_id=ctx.session_id):
        current_session_id.set(ctx.session_id)
        reset_buffer()
        engine = create_engine(ctx.cfg, language=ctx.language)
        try:
            await start_new_game(engine, ctx.repo, ctx.session_id, ctx.update, ctx.text)
        except Exception:
            logger.exception("Failed to start game for chat {}", chat_id)
            await ctx.repo.rollback()
            await ctx.update.message.reply_text("Something went wrong. Try /start again.")
            await ctx.repo.update_session(ctx.session_id, state=_STATE_IDLE)


async def handle_playing(ctx: Any) -> None:
    """Handle the 'playing' state: load game, process action, persist."""
    loaded = await load_game_or_reset(ctx.repo, ctx.session_id, ctx.update)
    if loaded is None:
        return

    game_state, kg, events = loaded
    engine = await create_engine_from_state(ctx.cfg, game_state, kg, events, language=ctx.language)

    with logger.contextualize(session_id=ctx.session_id):
        current_session_id.set(ctx.session_id)
        reset_buffer()
        try:
            await process_player_action(engine, ctx.repo, ctx.session_id, ctx.update, ctx.text)
        except Exception:
            logger.exception("Error processing action for session {}", ctx.session_id)
            await ctx.update.message.reply_text("Something went wrong processing your action. Try again.")


async def load_game_or_reset(
    repo: GameRepository,
    session_id: str,
    update: Any,
) -> tuple | None:
    """Load game state; if missing, notify user and reset session."""
    loaded = await repo.load_game_state(session_id)
    if loaded is None:
        await update.message.reply_text("No game found. Send /start to begin.")
        await repo.update_session(session_id, state=_STATE_IDLE)
    return loaded
