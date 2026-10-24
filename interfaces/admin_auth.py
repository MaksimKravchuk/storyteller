"""Admin dashboard auth helpers: the API is gated by the account admin role, not a shared token."""

from __future__ import annotations

from aiohttp import web

from config import Config
from interfaces import admin_route_helpers
from interfaces.web.auth import verify_supabase_token
from interfaces.web.auth_routes import get_public_config

_HTTP_UNAUTHORIZED = 401
_HTTP_FORBIDDEN = 403


async def admin_denial(request: web.Request, cfg: Config) -> web.Response | None:
    """Return a 401/403 response unless the bearer token belongs to an admin account."""
    token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    try:
        claims = await verify_supabase_token(token, cfg)
    except Exception:
        return admin_route_helpers._json_response({"error": "Unauthorized"}, status=_HTTP_UNAUTHORIZED)
    async with admin_route_helpers.open_repo(request) as repo:
        account = await repo.accounts.get_by_supabase_user_id(claims.sub)
    if account is None or not account.get("is_admin"):
        return admin_route_helpers._json_response({"error": "Admin role required"}, status=_HTTP_FORBIDDEN)
    return None


async def public_config(request: web.Request) -> web.Response:
    """Browser-safe Supabase settings so the dashboard can sign the admin in."""
    return web.json_response(await get_public_config(admin_route_helpers.get_cfg(request)))
