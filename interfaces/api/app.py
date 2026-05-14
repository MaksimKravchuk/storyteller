"""FastAPI app factory for the Storyteller mobile API.

Run in development with::

    uv run uvicorn interfaces.api.app:app --reload --host 127.0.0.1 --port 8071
"""

from __future__ import annotations

from fastapi import FastAPI

from interfaces.api.routes import router


def create_app() -> FastAPI:
    """Create the FastAPI application instance for the mobile API."""
    fastapi_app = FastAPI(title="Storyteller API", version="0.1.0")
    fastapi_app.include_router(router)
    return fastapi_app


app = create_app()
