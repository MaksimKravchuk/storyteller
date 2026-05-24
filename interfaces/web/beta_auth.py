"""FastAPI dependencies for beta-auth player identity."""

from __future__ import annotations

import typing

from fastapi import Depends, Request

from config import Config
from interfaces.web.auth import get_current_user, is_auth_required
from interfaces.web.deps import get_cfg, get_player_id, get_repo


async def get_beta_player_id(
    request: Request,
    cfg: typing.Annotated[Config, Depends(get_cfg)],
    repo: typing.Annotated[typing.Any, Depends(get_repo)],
    player_id: typing.Annotated[str, Depends(get_player_id)],
) -> str:
    """Return the legacy player id or authenticated account id when beta auth is enabled."""
    if not is_auth_required(cfg):
        return player_id
    user = await get_current_user(request, cfg, repo)
    return user.account_id
