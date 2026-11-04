"""Shared helpers for admin route handlers."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from config import Config
from db.engine import get_db
from db.repository import GameRepository
from interfaces.web import deps

_HTTP_NOT_FOUND = 404
_SESSION_ID_PARAM = "id"


def _resolve(request: Request, dependency: Any) -> Any:
    """Call a web ``deps`` provider, honouring ``app.dependency_overrides`` (tests)."""
    return request.app.dependency_overrides.get(dependency, dependency)()


def get_cfg(request: Request) -> Config:
    """Return the process-wide ``Config`` shared with the player web UI."""
    return _resolve(request, deps.get_cfg)


@asynccontextmanager
async def open_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Yield a fresh DB session from the web app's session factory."""
    async with get_db(_resolve(request, deps.get_session_factory)) as db:
        yield db


@asynccontextmanager
async def open_repo(request: Request) -> AsyncIterator[GameRepository]:
    """Yield a GameRepository bound to a fresh DB session."""
    async with open_session(request) as db:
        yield GameRepository(db)


@asynccontextmanager
async def session_scope(request: Request) -> AsyncIterator[tuple[str, GameRepository]]:
    """Yield ``(session_id, repo)`` — the request's session_id plus a fresh repo."""
    session_id = request.path_params[_SESSION_ID_PARAM]
    async with open_repo(request) as repo:
        yield session_id, repo
