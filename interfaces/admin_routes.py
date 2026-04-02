"""Route handlers for the admin dashboard API."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Awaitable, Callable

from aiohttp import web

from db.engine import get_db
from db.repo_admin import AdminQueries, fetch_events
from db.repository import GameRepository
from interfaces.admin import (
    _DASHBOARD_HTML,
    _HTTP_NOT_FOUND,
    _SESSION_ID_PARAM,
    _json_response,
)

_DEFAULT_LIMIT = "50"
_DEFAULT_OFFSET = "0"


@asynccontextmanager
async def _open_repo(request: web.Request) -> AsyncIterator[GameRepository]:
    """Yield a GameRepository bound to a fresh DB session."""
    db_factory = request.app["_db_factory"]
    async with get_db(db_factory) as db:
        yield GameRepository(db)


async def _session_repo_response(
    request: web.Request,
    fetch: Callable[[AdminQueries, str], Awaitable[Any]],
    key: str,
) -> web.Response:
    """Open a repo, fetch session data by id, and return a JSON response."""
    session_id = request.match_info[_SESSION_ID_PARAM]
    async with _open_repo(request) as repo:
        fetched = await fetch(repo.admin, session_id)
    return _json_response({key: fetched})


async def dashboard(request: web.Request) -> web.Response:
    """Serve the dashboard HTML page."""
    if _DASHBOARD_HTML.exists():
        return web.Response(
            text=_DASHBOARD_HTML.read_text(),
            content_type="text/html",
        )
    return web.Response(text="Dashboard HTML not found", status=_HTTP_NOT_FOUND)


async def list_sessions(request: web.Request) -> web.Response:
    """Return a paginated list of game sessions."""
    limit = int(request.query.get("limit", _DEFAULT_LIMIT))
    offset = int(request.query.get("offset", _DEFAULT_OFFSET))
    async with _open_repo(request) as repo:
        sessions = await repo.admin.list_sessions(limit=limit, offset=offset)
    return _json_response({"sessions": sessions})


async def session_detail(request: web.Request) -> web.Response:
    """Return details for a single session."""
    session_id = request.match_info[_SESSION_ID_PARAM]
    async with _open_repo(request) as repo:
        detail = await repo.admin.get_session_detail(session_id)
    if not detail:
        return _json_response({"error": "Session not found"}, status=_HTTP_NOT_FOUND)
    return _json_response(detail)


async def conversation(request: web.Request) -> web.Response:
    """Return the conversation log for a session."""
    return await _session_repo_response(request, _fetch_conversation, "log")


async def _fetch_conversation(admin: AdminQueries, session_id: str) -> Any:
    return await admin.get_conversation_log(session_id)


async def knowledge(request: web.Request) -> web.Response:
    """Return the knowledge graph for a session."""
    session_id = request.match_info[_SESSION_ID_PARAM]
    async with _open_repo(request) as repo:
        graph = await repo.admin.get_knowledge_graph(session_id)
    return _json_response(graph)


async def events(request: web.Request) -> web.Response:
    """Return events for a session."""
    return await _session_repo_response(request, _fetch_events, "events")


async def _fetch_events(admin: AdminQueries, session_id: str) -> Any:
    return await fetch_events(admin.session, session_id)


async def npcs(request: web.Request) -> web.Response:
    """Return NPCs for a session."""
    return await _session_repo_response(request, _fetch_npcs, "npcs")


async def _fetch_npcs(admin: AdminQueries, session_id: str) -> Any:
    return await admin.get_npcs(session_id)


async def locations(request: web.Request) -> web.Response:
    """Return locations for a session."""
    return await _session_repo_response(request, _fetch_locations, "locations")


async def _fetch_locations(admin: AdminQueries, session_id: str) -> Any:
    return await admin.get_locations(session_id)


async def ai_calls(request: web.Request) -> web.Response:
    """Return AI call logs for a session."""
    session_id = request.match_info[_SESSION_ID_PARAM]
    turn = request.query.get("turn")
    async with _open_repo(request) as repo:
        logs = await repo.get_ai_call_logs(
            session_id,
            turn_number=int(turn) if turn else None,
        )
    return _json_response({"ai_calls": logs})
