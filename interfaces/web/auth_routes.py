"""Auth and public browser-config routes for the player web UI."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from config import Config
from db.repository import GameRepository
from interfaces.web.auth import get_current_user
from interfaces.web.auth_models import AuthenticatedUser
from interfaces.web.deps import get_cfg, get_repo
from interfaces.web.poster_art import posters_available

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
        "supabase_publishable_key": cfg.public_supabase_key,
        "beta_auth_required": cfg.beta_auth_required,
        "beta_invite_gate_enabled": cfg.beta_invite_gate_enabled,
        "poster_images_enabled": posters_available(cfg),
    }


class PreferencesUpdate(BaseModel):
    """Body of ``PUT /api/me/preferences``."""

    mature_content: bool


@router.get("/api/me")
async def get_me(user: CurrentUserDep) -> dict[str, str | bool]:
    """Return the current authenticated beta account metadata."""
    return _me(user, user.mature_content)


@router.put("/api/me/preferences")
async def put_preferences(body: PreferencesUpdate, user: CurrentUserDep, repo: RepoDep) -> dict[str, str | bool]:
    """Store the account's 18+ switch; it applies from the next turn on."""
    await repo.accounts.set_mature_content(user.account_id, body.mature_content)
    return _me(user, body.mature_content)


def _me(user: AuthenticatedUser, mature_content: bool) -> dict[str, str | bool]:
    return {
        "account_id": user.account_id,
        "email": user.email,
        "plan": user.plan,
        "is_admin": user.is_admin,
        "mature_content": mature_content,
    }
