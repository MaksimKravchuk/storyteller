"""Detail route handlers for the admin dashboard API."""

from __future__ import annotations

from aiohttp import web

from interfaces.admin import _SESSION_ID_PARAM, _json_response
from interfaces import admin_route_helpers as helpers


async def knowledge(request: web.Request) -> web.Response:
    """Return the knowledge graph for a session."""
    session_id = request.match_info[_SESSION_ID_PARAM]
    async with helpers.open_repo(request) as repo:
        graph = await repo.admin.get_knowledge_graph(session_id)
    return _json_response(graph)


async def events(request: web.Request) -> web.Response:
    """Return events for a session."""
    return await helpers.session_repo_response(request, helpers.fetch_events_for_session, "events")


async def npcs(request: web.Request) -> web.Response:
    """Return NPCs for a session."""
    return await helpers.session_repo_response(request, helpers.fetch_npcs, "npcs")


async def locations(request: web.Request) -> web.Response:
    """Return locations for a session."""
    return await helpers.session_repo_response(request, helpers.fetch_locations, "locations")


async def ai_calls(request: web.Request) -> web.Response:
    """Return AI call logs for a session."""
    session_id = request.match_info[_SESSION_ID_PARAM]
    turn = request.query.get("turn")
    async with helpers.open_repo(request) as repo:
        logs = await repo.get_ai_call_logs(
            session_id,
            turn_number=int(turn) if turn else None,
        )
    return _json_response({"ai_calls": logs})
