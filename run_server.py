"""Production entry point — runs the Telegram bot, admin dashboard, and web UI."""

import asyncio
import logging
import os
import subprocess
import sys
import types

from loguru import logger

from config import load_config
from db import engine as db_engine
from interfaces.admin import AdminServer
from interfaces.telegram_bot import build_bot
from interfaces.web.runner import build_web_server

_ADMIN_PORT = 8080
_LOG_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan> | "
    "session=<yellow>{extra[session_id]}</yellow> | "
    "{message}"
)


class _InterceptHandler(logging.Handler):
    """Route stdlib logging (telegram, aiohttp, …) through loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        frame: types.FrameType | None = sys._getframe(6)  # noqa: WPS437
        depth = 6
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        log_message = record.getMessage()
        try:
            logger.opt(depth=depth, exception=record.exc_info).log(level, log_message)
        except Exception as exc:
            sys.stderr.write(
                f"_InterceptHandler: loguru failed ({type(exc).__name__}: {exc}). "
                f"Original: [{record.levelname}] {record.name}: {record.getMessage()}\n"
            )


logger.configure(
    handlers=[{"sink": sys.stdout, "format": _LOG_FORMAT, "level": "DEBUG", "colorize": True}],
    extra={"session_id": "-"},
)
logging.basicConfig(handlers=[_InterceptHandler()], level=0, force=True)


def _run_migrations() -> None:
    """Apply pending Alembic migrations before starting."""
    logger.info("Running database migrations...")
    proc = subprocess.run(  # noqa: S603,S607
        ["uv", "run", "alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        logger.error(
            "Migration failed (exit code {}).\nstdout:\n{}\nstderr:\n{}",
            proc.returncode,
            proc.stdout or "(empty)",
            proc.stderr or "(empty)",
        )
        sys.exit(1)
    logger.info("Migrations complete.")


async def _run_telegram_bot(cfg, session_factory) -> None:
    """Initialize, start, and poll the Telegram bot until shutdown."""
    bot = build_bot(cfg, session_factory)
    async with bot:
        await bot.initialize()
        await bot.start()
        assert bot.updater is not None  # noqa: S101
        await bot.updater.start_polling()
        logger.info("Telegram bot polling started.")
        await asyncio.Event().wait()


async def _run_until_first_completes(tasks: list[asyncio.Task]) -> None:
    """Await tasks in parallel; when one finishes (or fails), cancel the rest.

    Used so a clean uvicorn shutdown (SIGTERM → server.serve() returns) also
    stops the telegram bot's infinite polling loop, instead of waiting for
    Fly's SIGKILL.
    """
    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    for pending_task in pending:
        pending_task.cancel()
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)
    # Re-raise the first non-cancelled exception, if any, so the parent logs it.
    for finished in done:
        if not finished.cancelled() and finished.exception() is not None:
            raise finished.exception()  # type: ignore[misc]


async def _run_servers(cfg, session_factory) -> None:
    """Run the web UI and (optionally) the telegram bot until one finishes."""
    web_server = build_web_server(cfg.web_port)
    tasks = [asyncio.create_task(web_server.serve(), name="web")]
    if cfg.telegram_bot_token:
        tasks.append(asyncio.create_task(_run_telegram_bot(cfg, session_factory), name="telegram"))
        logger.info("Booting web UI on :{} and Telegram bot polling.", cfg.web_port)
    else:
        logger.warning("TELEGRAM_BOT_TOKEN not set — bot disabled, admin + web only.")
    await _run_until_first_completes(tasks)


async def main() -> None:
    cfg = load_config()
    engine = db_engine.create_async_engine(os.environ["DATABASE_URL"])
    session_factory = db_engine.create_session_factory(engine)

    admin = AdminServer(
        session_factory,
        port=_ADMIN_PORT,
        token=os.getenv("ADMIN_TOKEN"),
    )
    await admin.start()

    try:
        await _run_servers(cfg, session_factory)
    except Exception:
        logger.exception("Fatal error in main loop")
        raise
    finally:
        await admin.stop()
        await engine.dispose()


if __name__ == "__main__":
    _run_migrations()
    asyncio.run(main())
