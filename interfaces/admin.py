"""Admin dashboard — aiohttp web server for inspecting game sessions."""

from __future__ import annotations

from aiohttp import web
from aiohttp.typedefs import Handler
from loguru import logger

from interfaces import admin_routes, admin_routes_detail, admin_routes_entity
from interfaces.admin_route_helpers import _json_response

_HTTP_UNAUTHORIZED = 401


@web.middleware
async def _auth_middleware(request: web.Request, handler: Handler) -> web.StreamResponse:  # noqa: WPS110
    """Bearer-token auth middleware for API routes."""
    token = request.app.get("_auth_token")
    if token and request.path.startswith("/api/"):
        auth = request.headers.get("Authorization", "")
        if auth != "Bearer {0}".format(token):
            return _json_response({"error": "Unauthorized"}, status=_HTTP_UNAUTHORIZED)
    return await handler(request)


async def _healthz(_request: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


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

    @property
    def bound_address(self) -> tuple[str, int] | None:
        """Return (host, port) the server is bound to, or None if not started."""
        if self._runner is None:
            return None
        sockets = self._runner.addresses
        if not sockets:
            return None
        host, port = sockets[0][:2]
        return host, port

    def _setup_routes(self) -> None:
        self._app.router.add_get("/healthz", _healthz)
        self._app.router.add_get("/", admin_routes.dashboard)
        self._app.router.add_get("/api/sessions", admin_routes.list_sessions)
        self._app.router.add_get("/api/sessions/{id}", admin_routes.session_detail)
        self._app.router.add_get("/api/sessions/{id}/conversation", admin_routes.conversation)
        self._setup_detail_routes()

    def _setup_detail_routes(self) -> None:
        self._app.router.add_get("/api/sessions/{id}/knowledge", admin_routes_detail.knowledge)
        self._app.router.add_get("/api/sessions/{id}/events", admin_routes_detail.events)
        self._app.router.add_get("/api/sessions/{id}/npcs", admin_routes_detail.npcs)
        self._app.router.add_get("/api/sessions/{id}/npcs/{npc_id}", admin_routes_entity.npc_detail)
        self._app.router.add_get("/api/sessions/{id}/locations", admin_routes_detail.locations)
        self._app.router.add_get("/api/sessions/{id}/scenes", admin_routes_detail.scenes)
        self._app.router.add_get("/api/sessions/{id}/ai-calls", admin_routes_detail.ai_calls)
        self._app.router.add_get("/api/sessions/{id}/turn-events", admin_routes_entity.turn_events)
