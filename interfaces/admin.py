"""Admin dashboard — aiohttp web server for inspecting game sessions."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from aiohttp import web
from aiohttp.typedefs import Handler

from db.engine import get_db
from db.repository import GameRepository

logger = logging.getLogger(__name__)

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


class AdminServer:
    """Lightweight admin dashboard for inspecting Storyteller sessions."""

    def __init__(self, db_session_factory, *, port: int = 8080, token: str | None = None):
        self._db_factory = db_session_factory
        self._port = port
        self._token = token
        self._app = web.Application(middlewares=[self._build_auth_middleware()])
        self._setup_routes()
        self._runner: web.AppRunner | None = None

    async def start(self) -> None:
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "0.0.0.0", self._port)
        await site.start()
        logger.info("Admin dashboard running on http://0.0.0.0:%d", self._port)

    async def stop(self) -> None:
        if self._runner:
            await self._runner.cleanup()

    def _setup_routes(self) -> None:
        self._app.router.add_get("/", self._dashboard)
        self._app.router.add_get("/api/sessions", self._list_sessions)
        self._app.router.add_get("/api/sessions/{id}", self._session_detail)
        self._app.router.add_get("/api/sessions/{id}/conversation", self._conversation)
        self._app.router.add_get("/api/sessions/{id}/knowledge", self._knowledge)
        self._app.router.add_get("/api/sessions/{id}/events", self._events)
        self._app.router.add_get("/api/sessions/{id}/npcs", self._npcs)
        self._app.router.add_get("/api/sessions/{id}/locations", self._locations)
        self._app.router.add_get("/api/sessions/{id}/ai-calls", self._ai_calls)

    def _build_auth_middleware(self) -> Handler:
        @web.middleware
        async def auth_middleware(request: web.Request, handler: Handler) -> web.StreamResponse:  # noqa: WPS110
            if self._token and request.path.startswith("/api/"):
                auth = request.headers.get("Authorization", "")
                if auth != f"Bearer {self._token}":
                    return _json_response({"error": "Unauthorized"}, status=401)
            return await handler(request)

        return auth_middleware  # type: ignore[return-value]

    # ── Route handlers ────────────────────────────────────

    async def _dashboard(self, request: web.Request) -> web.Response:
        if _DASHBOARD_HTML.exists():
            return web.Response(
                text=_DASHBOARD_HTML.read_text(),
                content_type="text/html",
            )
        return web.Response(text="Dashboard HTML not found", status=404)

    async def _list_sessions(self, request: web.Request) -> web.Response:
        limit = int(request.query.get("limit", "50"))
        offset = int(request.query.get("offset", "0"))
        async with get_db(self._db_factory) as db:
            repo = GameRepository(db)
            sessions = await repo.list_sessions(limit=limit, offset=offset)
        return _json_response({"sessions": sessions})

    async def _session_detail(self, request: web.Request) -> web.Response:
        session_id = request.match_info["id"]
        async with get_db(self._db_factory) as db:
            repo = GameRepository(db)
            detail = await repo.get_session_detail(session_id)
        if not detail:
            return _json_response({"error": "Session not found"}, status=404)
        return _json_response(detail)

    async def _conversation(self, request: web.Request) -> web.Response:
        session_id = request.match_info["id"]
        async with get_db(self._db_factory) as db:
            repo = GameRepository(db)
            log = await repo.get_conversation_log(session_id)
        return _json_response({"log": log})

    async def _knowledge(self, request: web.Request) -> web.Response:
        session_id = request.match_info["id"]
        async with get_db(self._db_factory) as db:
            repo = GameRepository(db)
            graph = await repo.get_knowledge_graph(session_id)
        return _json_response(graph)

    async def _events(self, request: web.Request) -> web.Response:
        session_id = request.match_info["id"]
        async with get_db(self._db_factory) as db:
            repo = GameRepository(db)
            events = await repo.get_events(session_id)
        return _json_response({"events": events})

    async def _npcs(self, request: web.Request) -> web.Response:
        session_id = request.match_info["id"]
        async with get_db(self._db_factory) as db:
            repo = GameRepository(db)
            npcs = await repo.get_npcs(session_id)
        return _json_response({"npcs": npcs})

    async def _locations(self, request: web.Request) -> web.Response:
        session_id = request.match_info["id"]
        async with get_db(self._db_factory) as db:
            repo = GameRepository(db)
            locations = await repo.get_locations(session_id)
        return _json_response({"locations": locations})

    async def _ai_calls(self, request: web.Request) -> web.Response:
        session_id = request.match_info["id"]
        turn = request.query.get("turn")
        turn_number = int(turn) if turn else None
        async with get_db(self._db_factory) as db:
            repo = GameRepository(db)
            logs = await repo.get_ai_call_logs(session_id, turn_number=turn_number)
        return _json_response({"ai_calls": logs})
