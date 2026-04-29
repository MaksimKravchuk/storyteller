"""Telegram message handler logic — extracted from telegram_bot."""

from __future__ import annotations

from typing import Any

from loguru import logger

from engine.session_ops import begin_session, persist_engine_state, resume_session
from interfaces.telegram_handlers_helpers import recover_from_start_failure, _STATE_IDLE
from formatting.markdown_render import render
from formatting.platform import ClientPlatform

_TELEGRAM_PARSE_MODE = "HTML"


async def start_new_game(engine: Any, repo: Any, session_id: str, update: Any, text: str) -> None:
    """Run start_game and persist. Extracted to keep try-body short."""
    opening = await engine.start_game(text)
    await persist_engine_state(repo, session_id, engine, turn_number=None)
    await repo.sessions.update(session_id, state="playing")
    await update.message.reply_text(
        render(opening, ClientPlatform.TELEGRAM_HTML),
        parse_mode=_TELEGRAM_PARSE_MODE,
    )


async def process_player_action(engine: Any, repo: Any, session_id: str, update: Any, text: str) -> None:
    """Run process_action and persist. Extracted to keep try-body short."""
    response = await engine.process_action(text)
    game_state, _, _ = engine.assert_running()
    await persist_engine_state(repo, session_id, engine, turn_number=game_state.turn_count)
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
        engine = await begin_session(ctx.repo, ctx.cfg, ctx.session_id, ctx.language)
        try:
            await start_new_game(engine, ctx.repo, ctx.session_id, ctx.update, ctx.text)
        except Exception:
            await recover_from_start_failure(ctx, chat_id)


async def handle_playing(ctx: Any) -> None:
    """Handle the 'playing' state: load game, process action, persist."""
    with logger.contextualize(session_id=ctx.session_id):
        engine = await resume_session(ctx.repo, ctx.cfg, ctx.session_id, ctx.language)
        if engine is None:
            await ctx.update.message.reply_text("No game found. Send /start to begin.")
            await ctx.repo.sessions.update(ctx.session_id, state=_STATE_IDLE)
            return
        try:
            await process_player_action(engine, ctx.repo, ctx.session_id, ctx.update, ctx.text)
        except Exception:
            logger.exception("Error processing action for session {}", ctx.session_id)
            await ctx.update.message.reply_text("Something went wrong processing your action. Try again.")
