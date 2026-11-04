"""Admin dashboard auth: the API is gated by the account admin role, not a shared token."""

from __future__ import annotations

from fastapi import HTTPException, Request

from interfaces import admin_route_helpers
from interfaces.web.auth import is_auth_required, verify_supabase_token

_HTTP_UNAUTHORIZED = 401
_HTTP_FORBIDDEN = 403


async def require_admin(request: Request) -> None:
    """Raise 401/403 unless auth is off (local dev) or the bearer token belongs to an admin account."""
    cfg = admin_route_helpers.get_cfg(request)
    if not is_auth_required(cfg):
        return
    token = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    try:
        claims = await verify_supabase_token(token, cfg)
    except Exception as exc:
        raise HTTPException(_HTTP_UNAUTHORIZED, "Unauthorized") from exc
    async with admin_route_helpers.open_repo(request) as repo:
        account = await repo.accounts.get_by_supabase_user_id(claims.sub)
    if account is None or not account.get("is_admin"):
        raise HTTPException(_HTTP_FORBIDDEN, "Admin role required")
