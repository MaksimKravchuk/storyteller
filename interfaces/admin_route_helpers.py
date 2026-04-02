"""Shared helpers for admin route handlers."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator

from aiohttp import web

from db.engine import get_db
from db.repository import GameRepository

_HTTP_NOT_FOUND = 404
_SESSION_ID_PARAM = "id"
_DASHBOARD_HTML = Path(__file__).parent / "admin_dashboard.html"


def _json_serial(unknown: Any) -> Any:
    """JSON serializer for objects not handled by default json."""
    if isinstance(unknown, datetime):
        return unknown.isoformat()
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
    db_factory = request.app["_db_factory"]
    async with get_db(db_factory) as db:
        yield GameRepository(db)
