"""Admin dashboard — FastAPI router mounted at ``/admin`` for inspecting game sessions."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from interfaces import admin_reports, admin_routes, admin_routes_beta_invites, admin_routes_detail
from interfaces import admin_routes_entity, admin_routes_feedback, admin_routes_reliability
from interfaces import admin_routes_settings, admin_routes_settings_search
from interfaces.admin_auth import require_admin

_GET = "GET"
_ROUTES = (
    (_GET, "/sessions", admin_routes.list_sessions),
    (_GET, "/sessions/{id}", admin_routes.session_detail),
    (_GET, "/sessions/{id}/conversation", admin_routes.conversation),
    (_GET, "/sessions/{id}/knowledge", admin_routes_detail.knowledge),
    (_GET, "/sessions/{id}/events", admin_routes_detail.events),
    (_GET, "/sessions/{id}/npcs", admin_routes_detail.npcs),
    (_GET, "/sessions/{id}/npcs/{npc_id}", admin_routes_entity.npc_detail),
    (_GET, "/sessions/{id}/locations", admin_routes_detail.locations),
    (_GET, "/sessions/{id}/scenes", admin_routes_detail.scenes),
    (_GET, "/sessions/{id}/ai-calls", admin_routes_detail.ai_calls),
    (_GET, "/sessions/{id}/turn-events", admin_routes_entity.turn_events),
    (_GET, "/sessions/{id}/models", admin_routes_detail.session_models),
    (_GET, "/admin/users", admin_routes.list_users),
    (_GET, "/admin/users/{id}", admin_routes.user_detail),
    (_GET, "/admin/beta/cost-summary", admin_reports.beta_cost_summary),
    (_GET, "/admin/beta/feedback", admin_routes_feedback.list_feedback),
    (_GET, "/admin/beta/feedback.csv", admin_routes_feedback.export_feedback_csv),
    (_GET, "/admin/beta/invites", admin_routes_beta_invites.list_beta_invites),
    ("POST", "/admin/beta/invites", admin_routes_beta_invites.create_beta_invite),
    (_GET, "/admin/reliability", admin_routes_reliability.reliability_summary),
    (_GET, "/settings/keys", admin_routes_settings.get_keys),
    (_GET, "/settings/models", admin_routes_settings.get_models),
    ("POST", "/settings/models", admin_routes_settings.set_model),
    (_GET, "/settings/search", admin_routes_settings_search.get_search),
    ("POST", "/settings/search", admin_routes_settings_search.set_search),
    ("DELETE", "/settings/search", admin_routes_settings_search.clear_search),
)


def _build_router() -> APIRouter:
    """Dashboard page (open) plus the admin-gated ``/api`` routes, all under ``/admin``."""
    admin_router = APIRouter(prefix="/admin", include_in_schema=False)
    api = APIRouter(prefix="/api", dependencies=[Depends(require_admin)])
    for path in ("", "/"):
        admin_router.add_api_route(path, admin_routes.dashboard, methods=[_GET])
    for method, path, endpoint in _ROUTES:
        api.add_api_route(path, endpoint, methods=[method])
    admin_router.include_router(api)
    return admin_router


router = _build_router()
