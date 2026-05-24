"""Shared helpers for admin route handlers."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any, AsyncIterator
from uuid import UUID

from aiohttp import web

from config import Config
from db.engine import get_db
from db.repository import GameRepository

_HTTP_NOT_FOUND = 404
_SESSION_ID_PARAM = "id"
_DASHBOARD_HTML = Path(__file__).parent / "admin_dashboard.html"
AUTH_TOKEN_KEY: web.AppKey[str] = web.AppKey("storyteller_admin_auth_token", str)
CFG_KEY: web.AppKey[Config] = web.AppKey("storyteller_admin_cfg", Config)
DB_FACTORY_KEY: web.AppKey[Any] = web.AppKey("storyteller_admin_db_factory", object)


def get_cfg(request: web.Request) -> Config:
    """Return the ``Config`` object stored on the admin app."""
    return request.app[CFG_KEY]


def _json_serial(unknown: Any) -> Any:
    """JSON serializer for objects not handled by default json."""
    if isinstance(unknown, (date, datetime)):
        return unknown.isoformat()
    if isinstance(unknown, UUID):
        return str(unknown)
    raise TypeError(f"Type {type(unknown)} not serializable")


def _json_response(payload: Any, status: int = 200) -> web.Response:
    return web.Response(
        text=json.dumps(payload, default=_json_serial),
        content_type="application/json",
        status=status,
    )


@asynccontextmanager
async def open_repo(request: web.Request) -> AsyncIterator[GameRepository]:
    """Yield a GameRepository bound to a fresh DB session."""
    db_factory = request.app[DB_FACTORY_KEY]
    async with get_db(db_factory) as db:
        yield GameRepository(db)


@asynccontextmanager
async def session_scope(request: web.Request) -> AsyncIterator[tuple[str, GameRepository]]:
    """Yield ``(session_id, repo)`` — the request's session_id plus a fresh repo."""
    session_id = request.match_info[_SESSION_ID_PARAM]
    async with open_repo(request) as repo:
        yield session_id, repo
