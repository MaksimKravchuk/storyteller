"""Storyteller — AI-powered text quest engine.

Unified entry-point: runs both the Telegram bot and the admin dashboard.
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys

from config import load_config
from db.engine import create_async_engine, create_session_factory

logger = logging.getLogger(__name__)


async def run_migrations(database_url: str) -> None:
    """Run Alembic migrations programmatically."""
    from alembic import command  # type: ignore[attr-defined]
    from alembic.config import Config as AlembicConfig  # type: ignore[attr-defined]

    alembic_cfg = AlembicConfig("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)
    # Run in a thread to avoid blocking the event loop
    await asyncio.to_thread(command.upgrade, alembic_cfg, "head")


async def async_main() -> None:
    """Run Telegram bot and admin server concurrently."""
    cfg = load_config()

    # Database setup
    engine = create_async_engine(cfg.database_url)
    db_session_factory = create_session_factory(engine)

    # Run migrations
    logger.info("Running database migrations...")
    try:
        await run_migrations(cfg.database_url)
        logger.info("Migrations complete.")
    except Exception:
        logger.exception("Migration failed — ensure PostgreSQL is running")
        await engine.dispose()
        sys.exit(1)

    # Build Telegram bot
    from interfaces.telegram_bot import build_bot

    bot_app = build_bot(cfg, db_session_factory)
    await bot_app.initialize()
    await bot_app.start()
    assert bot_app.updater is not None
    await bot_app.updater.start_polling()
    logger.info("Telegram bot started.")

    # Start admin server
    from interfaces.admin import AdminServer

    admin = AdminServer(
        db_session_factory,
        port=cfg.admin_port,
        token=cfg.admin_token,
    )
    await admin.start()

    # Wait for shutdown signal
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    logger.info("Storyteller is running. Press Ctrl+C to stop.")
    await stop.wait()

    # Graceful shutdown
    logger.info("Shutting down...")
    await admin.stop()
    if bot_app.updater:
        await bot_app.updater.stop()
    await bot_app.stop()
    await bot_app.shutdown()
    await engine.dispose()
    logger.info("Goodbye.")


def main_cli() -> None:
    """Original CLI entry-point for local testing (no DB required)."""
    from engine.factory import create_engine
    from interfaces.formatting_backends import PlainTextBackend
    from interfaces.text_styler import TextStyler

    cfg = load_config()
    engine = create_engine(cfg)
    styler = TextStyler(PlainTextBackend())

    sys.stdout.write(f"{'=' * 60}\n")
    sys.stdout.write("  STORYTELLER — AI Text Quest Engine (CLI mode)\n")
    sys.stdout.write(f"{'=' * 60}\n")
    sys.stdout.write(f"  Director: {cfg.director_model}\n")
    sys.stdout.write(f"  Agents:   {cfg.agent_model}\n")
    sys.stdout.write(f"  Narrator: {cfg.narrator_model}\n")
    sys.stdout.write(f"{'=' * 60}\n")
    sys.stdout.write("\n")

    async def _cli_loop():
        sys.stdout.write("Describe your desired setting (e.g. 'Rome, 1st century AD'): ")
        sys.stdout.flush()
        setting = sys.stdin.readline().rstrip("\n")
        sys.stdout.write("\nResearching setting and generating opening scene...\n\n")
        opening = await engine.start_game(setting)
        sys.stdout.write(f"{styler.format(opening)}\n")
        while True:
            sys.stdout.write("\n")
            sys.stdout.write("> ")
            sys.stdout.flush()
            action = sys.stdin.readline().rstrip("\n").strip()
            if not action:
                continue
            if action.lower() in ("quit", "exit", "q"):
                sys.stdout.write("Thanks for playing!\n")
                break
            response = await engine.process_action(action)
            sys.stdout.write("\n")
            sys.stdout.write(f"{styler.format(response)}\n")

    asyncio.run(_cli_loop())


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-5s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    if "--cli" in sys.argv:
        main_cli()
    else:
        asyncio.run(async_main())
