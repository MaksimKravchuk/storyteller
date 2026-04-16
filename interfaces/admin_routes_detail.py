"""Detail route handlers for the admin dashboard API."""

from __future__ import annotations

from aiohttp import web

from db.repo_admin import fetch_events, fetch_scenes
from interfaces import admin_route_helpers as helpers
from interfaces.admin_route_helpers import _json_response


async def knowledge(request: web.Request) -> web.Response:
    """Return the knowledge graph for a session."""
    async with helpers.session_scope(request) as (session_id, repo):
        graph = await repo.admin.get_knowledge_graph(session_id)
    return _json_response(graph)


async def events(request: web.Request) -> web.Response:
    """Return events for a session."""
    async with helpers.session_scope(request) as (session_id, repo):
        fetched = await fetch_events(repo.admin.session, session_id)
    return _json_response({"events": fetched})


async def npcs(request: web.Request) -> web.Response:
    """Return NPCs for a session."""
    async with helpers.session_scope(request) as (session_id, repo):
        fetched = await repo.admin.get_npcs(session_id)
    return _json_response({"npcs": fetched})


async def locations(request: web.Request) -> web.Response:
    """Return locations for a session."""
    async with helpers.session_scope(request) as (session_id, repo):
        fetched = await repo.admin.get_locations(session_id)
    return _json_response({"locations": fetched})


async def scenes(request: web.Request) -> web.Response:
    """Return all scenes (including historical) for a session."""
    async with helpers.session_scope(request) as (session_id, repo):
        fetched = await fetch_scenes(repo.admin.session, session_id)
    return _json_response({"scenes": fetched})


async def ai_calls(request: web.Request) -> web.Response:
    """Return AI call logs for a session."""
    turn = request.query.get("turn")
    async with helpers.session_scope(request) as (session_id, repo):
        logs = await repo.ai_logs.get(
            session_id,
            turn_number=int(turn) if turn else None,
        )
    return _json_response({"ai_calls": logs})
