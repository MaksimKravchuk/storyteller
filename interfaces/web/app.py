"""FastAPI app factory for the Storyteller web UI.

Run in development with::

    uv run uvicorn interfaces.web.app:app --reload
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from interfaces.web.deps import player_id_middleware
from interfaces.web.routes import router

_STATIC_DIR = Path(__file__).parent / "static"


def create_app() -> FastAPI:
    """Create the FastAPI application instance."""
    fastapi_app = FastAPI(title="Storyteller Web", version="0.1.0")
    fastapi_app.middleware("http")(player_id_middleware)
    fastapi_app.include_router(router)
    fastapi_app.mount(
        "/static",
        StaticFiles(directory=_STATIC_DIR),
        name="static",
    )
    return fastapi_app


app = create_app()
