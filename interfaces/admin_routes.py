"""Route handlers for the admin dashboard API."""

from __future__ import annotations

from pathlib import Path

from fastapi import Request
from starlette.responses import HTMLResponse, Response

from interfaces import admin_route_helpers as helpers
from interfaces.admin_json import _json_response
from interfaces.admin_route_helpers import _HTTP_NOT_FOUND, _SESSION_ID_PARAM

_DASHBOARD_HTML = Path(__file__).parent / "admin_dashboard.html"
_DEFAULT_LIMIT = "50"
_DEFAULT_OFFSET = "0"


def _session_list_filters(request: Request) -> dict:
    """Parse optional ``list_sessions`` filter/pagination params from the query string."""
    return {
        "limit": int(request.query_params.get("limit", _DEFAULT_LIMIT)),
        "offset": int(request.query_params.get("offset", _DEFAULT_OFFSET)),
        "web_player_id": request.query_params.get("web_player_id") or None,
        "search": request.query_params.get("search") or None,
    }


async def dashboard(request: Request) -> Response:
    """Serve the dashboard HTML page."""
    if _DASHBOARD_HTML.exists():
        return HTMLResponse(_DASHBOARD_HTML.read_text())
    return Response("Dashboard HTML not found", status_code=_HTTP_NOT_FOUND)


async def list_sessions(request: Request) -> Response:
    """Return a paginated list of game sessions, optionally filtered by player."""
    async with helpers.open_repo(request) as repo:
        sessions = await repo.admin.list_sessions(**_session_list_filters(request))
    return _json_response({"sessions": sessions})


async def list_users(request: Request) -> Response:
    """Return all user accounts with admin-facing aggregate counts."""
    email_query = request.query_params.get("email_query") or None
    async with helpers.open_repo(request) as repo:
        users = await repo.admin.list_users(email_query=email_query)
    return _json_response({"users": users})


async def user_detail(request: Request) -> Response:
    """Return account metadata, usage totals, and sessions for one user."""
    user_id = request.path_params["id"]
    async with helpers.open_repo(request) as repo:
        detail = await repo.admin.get_user_detail(user_id)
    if not detail:
        return _json_response({"error": "User not found"}, status=_HTTP_NOT_FOUND)
    return _json_response(detail)


async def session_detail(request: Request) -> Response:
    """Return details for a single session."""
    session_id = request.path_params[_SESSION_ID_PARAM]
    async with helpers.open_repo(request) as repo:
        detail = await repo.admin.get_session_detail(session_id)
    if not detail:
        return _json_response({"error": "Session not found"}, status=_HTTP_NOT_FOUND)
    return _json_response(detail)


async def conversation(request: Request) -> Response:
    """Return the conversation log for a session."""
    session_id = request.path_params[_SESSION_ID_PARAM]
    async with helpers.open_repo(request) as repo:
        log = await repo.admin.get_conversation_log(session_id)
    return _json_response({"log": log})
