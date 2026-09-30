"""FastAPI app factory for the Storyteller web UI.

Run in development with::

    uv run uvicorn interfaces.web.app:app --reload
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from interfaces.web.auth_routes import router as auth_router
from interfaces.web.deps import player_id_middleware
from interfaces.web.routes import router
from interfaces.web.routes_feedback import router as feedback_router
from interfaces.web.routes_library import router as library_router
from interfaces.web.routes_poster import router as poster_router

_STATIC_DIR = Path(__file__).parent / "static"
_GENERIC_PLAYER_ERROR = "Something went wrong. Please try again."


async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return a stable player-facing error while logging internals server-side."""
    logger.exception(
        "Unhandled web UI error while serving {} {}",
        request.method,
        request.url.path,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": _GENERIC_PLAYER_ERROR},
    )


def create_app() -> FastAPI:
    """Create the FastAPI application instance."""
    fastapi_app = FastAPI(title="Storyteller Web", version="0.1.0")
    fastapi_app.add_exception_handler(Exception, _unhandled_exception_handler)
    fastapi_app.middleware("http")(player_id_middleware)
    fastapi_app.include_router(auth_router)
    fastapi_app.include_router(router)
    fastapi_app.include_router(library_router)
    fastapi_app.include_router(feedback_router)
    fastapi_app.include_router(poster_router)
    fastapi_app.mount(
        "/static",
        StaticFiles(directory=_STATIC_DIR),
        name="static",
    )
    return fastapi_app


app = create_app()
