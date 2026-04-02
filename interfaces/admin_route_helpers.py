"""Shared helpers for admin route handlers."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Awaitable, Callable

from aiohttp import web

from db.engine import get_db
from db.repo_admin import AdminQueries, fetch_events
from db.repository import GameRepository
from interfaces.admin import _SESSION_ID_PARAM, _json_response


@asynccontextmanager
async def open_repo(request: web.Request) -> AsyncIterator[GameRepository]:
    """Yield a GameRepository bound to a fresh DB session."""
    db_factory = request.app["_db_factory"]
    async with get_db(db_factory) as db:
        yield GameRepository(db)


async def session_repo_response(
    request: web.Request,
    fetch: Callable[[AdminQueries, str], Awaitable[Any]],
    key: str,
) -> web.Response:
    """Open a repo, fetch session data by id, and return a JSON response."""
    session_id = request.match_info[_SESSION_ID_PARAM]
    async with open_repo(request) as repo:
        fetched = await fetch(repo.admin, session_id)
    return _json_response({key: fetched})


async def fetch_conversation(admin: AdminQueries, session_id: str) -> Any:
    """Fetch conversation log via admin queries."""
    return await admin.get_conversation_log(session_id)


async def fetch_events_for_session(admin: AdminQueries, session_id: str) -> Any:
    """Fetch events via admin queries."""
    return await fetch_events(admin.session, session_id)


async def fetch_npcs(admin: AdminQueries, session_id: str) -> Any:
    """Fetch NPCs via admin queries."""
    return await admin.get_npcs(session_id)


async def fetch_locations(admin: AdminQueries, session_id: str) -> Any:
    """Fetch locations via admin queries."""
    return await admin.get_locations(session_id)
