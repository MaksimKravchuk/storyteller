"""Detail route handlers for the admin dashboard API."""

from __future__ import annotations

from fastapi import Request
from starlette.responses import Response

from db.repo_admin import fetch_events, fetch_scenes
from db.repo_admin_models import fetch_session_models
from interfaces import admin_route_helpers as helpers
from interfaces.admin_json import _json_response


async def knowledge(request: Request) -> Response:
    """Return the knowledge graph for a session."""
    async with helpers.session_scope(request) as (session_id, repo):
        graph = await repo.admin.get_knowledge_graph(session_id)
    return _json_response(graph)


async def events(request: Request) -> Response:
    """Return events for a session."""
    async with helpers.session_scope(request) as (session_id, repo):
        fetched = await fetch_events(repo.admin.session, session_id)
    return _json_response({"events": fetched})


async def npcs(request: Request) -> Response:
    """Return NPCs for a session."""
    async with helpers.session_scope(request) as (session_id, repo):
        fetched = await repo.admin.get_npcs(session_id)
    return _json_response({"npcs": fetched})


async def locations(request: Request) -> Response:
    """Return locations for a session."""
    async with helpers.session_scope(request) as (session_id, repo):
        fetched = await repo.admin.get_locations(session_id)
    return _json_response({"locations": fetched})


async def scenes(request: Request) -> Response:
    """Return all scenes (including historical) for a session."""
    async with helpers.session_scope(request) as (session_id, repo):
        fetched = await fetch_scenes(repo.admin.session, session_id)
    return _json_response({"scenes": fetched})


async def ai_calls(request: Request) -> Response:
    """Return AI call logs for a session."""
    turn = request.query_params.get("turn")
    async with helpers.session_scope(request) as (session_id, repo):
        logs = await repo.ai_logs.get(
            session_id,
            turn_number=int(turn) if turn else None,
        )
    return _json_response({"ai_calls": logs})


async def session_models(request: Request) -> Response:
    """Return distinct (agent_name, model, calls) used in this session."""
    async with helpers.session_scope(request) as (session_id, repo):
        models = await fetch_session_models(repo.admin.session, session_id)
    return _json_response({"models": models})
