"""Per-entity admin routes: NPC detail + structured turn events."""

from __future__ import annotations

from aiohttp import web

from interfaces import admin_route_helpers as helpers
from interfaces.admin_route_helpers import _json_response


async def turn_events(request: web.Request) -> web.Response:
    """Return structured turn events (dice / items / ...) for a session."""
    turn = request.query.get("turn")
    async with helpers.session_scope(request) as (session_id, repo):
        fetched = await repo.turn_events.get(
            session_id,
            turn_number=int(turn) if turn else None,
            npc_id=request.query.get("npc_id") or None,
            event_type=request.query.get("event_type") or None,
        )
    return _json_response({"turn_events": fetched})


async def npc_detail(request: web.Request) -> web.Response:
    """Return one NPC's full row plus its memory graph subset."""
    npc_id = request.match_info["npc_id"]
    async with helpers.session_scope(request) as (session_id, repo):
        detail = await repo.admin.get_npc_detail(session_id, npc_id)
    if detail is None:
        return _json_response({"error": "NPC not found"}, status=helpers._HTTP_NOT_FOUND)
    return _json_response(detail)
