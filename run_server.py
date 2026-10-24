"""Production entry point — runs the admin dashboard and web UI."""

import asyncio
import logging
import os
import sys

from loguru import logger

from config import load_config
from db import engine as db_engine
from interfaces.admin import AdminServer
from interfaces.web.auth import is_auth_required
from interfaces.web.runner import build_web_server
from log_scrubbing import LOGURU_DIAGNOSE_ENABLED, scrub_log_record

_ADMIN_PORT = 8080
_LOG_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan> | "
    "session=<yellow>{extra[session_id]}</yellow> | "
    "{message}"
)


class _InterceptHandler(logging.Handler):
    """Route stdlib logging (aiohttp, uvicorn, ...) through loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        frame = sys._getframe(6)  # noqa: WPS437
        depth = 6
        while frame.f_code.co_filename == logging.__file__:
            next_frame = frame.f_back
            if next_frame is None:
                break
            frame = next_frame
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
    handlers=[
        {
            "sink": sys.stdout,
            "format": _LOG_FORMAT,
            "level": "DEBUG",
            "colorize": True,
            "diagnose": LOGURU_DIAGNOSE_ENABLED,
        },
    ],
    extra={"session_id": "-"},
    patcher=scrub_log_record,
)
logging.basicConfig(handlers=[_InterceptHandler()], level=0, force=True)


def _run_migrations() -> None:
    """Apply pending Alembic migrations before starting."""
    from alembic.config import main as alembic_main

    logger.info("Running database migrations...")
    alembic_main(argv=["upgrade", "head"])
    logger.info("Migrations complete.")


async def _run_server(cfg) -> None:
    """Run the web UI until shutdown."""
    web_server = build_web_server(cfg.web_port)
    logger.info("Booting web UI on :{}.", cfg.web_port)
    await web_server.serve()


def require_admin_auth_on_fly(cfg) -> None:
    """Refuse to boot a Fly deploy without beta auth: the admin API is gated by the account admin role."""
    if os.getenv("FLY_APP_NAME") and not is_auth_required(cfg):
        sys.exit("BETA_AUTH_REQUIRED must be true on Fly: without it the admin API on :8080 is open to anyone.")


async def main() -> None:
    cfg = load_config()
    require_admin_auth_on_fly(cfg)
    engine = db_engine.create_async_engine(os.environ["DATABASE_URL"])
    session_factory = db_engine.create_session_factory(engine)

    admin = AdminServer(session_factory, cfg, port=_ADMIN_PORT)
    await admin.start()

    try:
        await _run_server(cfg)
    except Exception:
        logger.exception("Fatal error in main loop")
        raise
    finally:
        await admin.stop()
        await engine.dispose()


if __name__ == "__main__":
    _run_migrations()
    asyncio.run(main())
