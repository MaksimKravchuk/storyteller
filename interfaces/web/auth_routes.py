"""Auth and public browser-config routes for the player web UI."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from config import Config
from db.repository import GameRepository
from interfaces.web.auth import get_current_user
from interfaces.web.auth_models import AuthenticatedUser
from interfaces.web.deps import get_cfg, get_repo

router = APIRouter()

CfgDep = Annotated[Config, Depends(get_cfg)]
RepoDep = Annotated[GameRepository, Depends(get_repo)]


async def current_user(request: Request, cfg: CfgDep, repo: RepoDep) -> AuthenticatedUser:
    """FastAPI wrapper for the current authenticated beta user."""
    return await get_current_user(request, cfg, repo)


CurrentUserDep = Annotated[AuthenticatedUser, Depends(current_user)]


@router.get("/api/config/public")
async def get_public_config(cfg: CfgDep) -> dict[str, str | bool | None]:
    """Return public browser config; never include server-side JWT settings."""
    return {
        "supabase_url": cfg.supabase_url,
        "supabase_anon_key": cfg.supabase_anon_key,
        "beta_auth_required": cfg.beta_auth_required,
        "beta_invite_gate_enabled": cfg.beta_invite_gate_enabled,
    }


@router.get("/api/me")
async def get_me(user: CurrentUserDep) -> dict[str, str | bool]:
    """Return the current authenticated beta account metadata."""
    return {
        "account_id": user.account_id,
        "email": user.email,
        "plan": user.plan,
        "is_admin": user.is_admin,
    }
