"""Admin dashboard — aiohttp web server for inspecting game sessions."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from aiohttp import web
from aiohttp.typedefs import Handler
from loguru import logger

_HTTP_UNAUTHORIZED = 401
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


@web.middleware
async def _auth_middleware(request: web.Request, handler: Handler) -> web.StreamResponse:  # noqa: WPS110
    """Bearer-token auth middleware for API routes."""
    token = request.app.get("_auth_token")
    if token and request.path.startswith("/api/"):
        auth = request.headers.get("Authorization", "")
        if auth != "Bearer {0}".format(token):
            return _json_response({"error": "Unauthorized"}, status=_HTTP_UNAUTHORIZED)
    return await handler(request)


class AdminServer:
    """Lightweight admin dashboard for inspecting Storyteller sessions."""

    def __init__(self, db_session_factory, *, port: int = 8080, token: str | None = None):
        self._port = port
        self._app = web.Application(middlewares=[_auth_middleware])
        self._app["_auth_token"] = token
        self._app["_db_factory"] = db_session_factory
        self._setup_routes()
        self._runner: web.AppRunner | None = None

    async def start(self) -> None:
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "0.0.0.0", self._port)
        await site.start()
        logger.info("Admin dashboard running on http://0.0.0.0:{}", self._port)

    async def stop(self) -> None:
        if self._runner:
            await self._runner.cleanup()

    def _setup_routes(self) -> None:
        from interfaces import admin_routes  # noqa: WPS433

        self._app.router.add_get("/", admin_routes.dashboard)
        self._app.router.add_get("/api/sessions", admin_routes.list_sessions)
        self._app.router.add_get("/api/sessions/{id}", admin_routes.session_detail)
        self._app.router.add_get("/api/sessions/{id}/conversation", admin_routes.conversation)
        self._app.router.add_get("/api/sessions/{id}/knowledge", admin_routes.knowledge)
        self._app.router.add_get("/api/sessions/{id}/events", admin_routes.events)
        self._app.router.add_get("/api/sessions/{id}/npcs", admin_routes.npcs)
        self._app.router.add_get("/api/sessions/{id}/locations", admin_routes.locations)
        self._app.router.add_get("/api/sessions/{id}/ai-calls", admin_routes.ai_calls)
