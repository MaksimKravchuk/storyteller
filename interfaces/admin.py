"""Admin dashboard — aiohttp web server for inspecting game sessions."""

from __future__ import annotations

from aiohttp import web
from aiohttp.typedefs import Handler
from loguru import logger

from config import Config
from interfaces import (
    admin_route_helpers,
    admin_reports,
    admin_routes,
    admin_routes_beta_invites,
    admin_routes_detail,
    admin_routes_entity,
    admin_routes_feedback,
    admin_routes_settings,
)
from interfaces import admin_routes_reliability

_HTTP_UNAUTHORIZED = 401


@web.middleware
async def _auth_middleware(request: web.Request, handler: Handler) -> web.StreamResponse:  # noqa: WPS110
    """Bearer-token auth middleware for API routes."""
    token = request.app.get(admin_route_helpers.AUTH_TOKEN_KEY)
    if token and request.path.startswith("/api/"):
        auth = request.headers.get("Authorization", "")
        if auth != "Bearer {0}".format(token):
            return admin_route_helpers._json_response(
                {"error": "Unauthorized"},
                status=_HTTP_UNAUTHORIZED,
            )
    return await handler(request)


async def _healthz(_request: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


def _setup_session_report_routes(app: web.Application) -> None:
    """Register session detail and beta-cost report routes."""
    app.router.add_get("/api/admin/beta/cost-summary", admin_reports.beta_cost_summary)
    app.router.add_get("/api/sessions/{id}/scenes", admin_routes_detail.scenes)
    app.router.add_get("/api/sessions/{id}/ai-calls", admin_routes_detail.ai_calls)
    app.router.add_get("/api/sessions/{id}/turn-events", admin_routes_entity.turn_events)
    app.router.add_get("/api/sessions/{id}/models", admin_routes_detail.session_models)


def _setup_beta_and_reliability_routes(app: web.Application) -> None:
    """Register admin beta-feedback and reliability dashboard routes."""
    app.router.add_get("/api/admin/beta/feedback", admin_routes_feedback.list_feedback)
    app.router.add_get("/api/admin/beta/feedback.csv", admin_routes_feedback.export_feedback_csv)
    app.router.add_get("/api/admin/reliability", admin_routes_reliability.reliability_summary)


def _setup_user_routes(app: web.Application) -> None:
    """Register admin user-management routes."""
    app.router.add_get("/api/admin/users", admin_routes.list_users)
    app.router.add_get("/api/admin/users/{id}", admin_routes.user_detail)
    app.router.add_get("/api/admin/beta/invites", admin_routes_beta_invites.list_beta_invites)
    app.router.add_post("/api/admin/beta/invites", admin_routes_beta_invites.create_beta_invite)


class AdminServer:
    """Lightweight admin dashboard for inspecting Storyteller sessions."""

    def __init__(
        self,
        db_session_factory,
        cfg: Config,
        *,
        port: int = 8080,
        token: str | None = None,
    ):
        self._port = port
        self._app = web.Application(middlewares=[_auth_middleware])
        if token is not None:
            self._app[admin_route_helpers.AUTH_TOKEN_KEY] = token
        self._app[admin_route_helpers.DB_FACTORY_KEY] = db_session_factory
        self._app[admin_route_helpers.CFG_KEY] = cfg
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
        _setup_user_routes(self._app)
        _setup_beta_and_reliability_routes(self._app)
        self._app.router.add_get("/api/sessions/{id}", admin_routes.session_detail)
        self._app.router.add_get("/api/sessions/{id}/conversation", admin_routes.conversation)
        self._setup_detail_routes()
        self._setup_settings_routes()

    def _setup_settings_routes(self) -> None:
        self._app.router.add_get("/api/settings/keys", admin_routes_settings.get_keys)
        self._app.router.add_get("/api/settings/models", admin_routes_settings.get_models)
        self._app.router.add_post("/api/settings/models", admin_routes_settings.set_model)

    def _setup_detail_routes(self) -> None:
        self._app.router.add_get("/api/sessions/{id}/knowledge", admin_routes_detail.knowledge)
        self._app.router.add_get("/api/sessions/{id}/events", admin_routes_detail.events)
        self._app.router.add_get("/api/sessions/{id}/npcs", admin_routes_detail.npcs)
        self._app.router.add_get("/api/sessions/{id}/npcs/{npc_id}", admin_routes_entity.npc_detail)
        self._app.router.add_get("/api/sessions/{id}/locations", admin_routes_detail.locations)
        _setup_session_report_routes(self._app)
