"""FastAPI dependencies for beta-auth player identity."""

from __future__ import annotations

import typing

from fastapi import Depends, Request

from config import Config
from interfaces.web.auth import get_current_user, is_auth_required
from interfaces.web.auth_models import PlayerFeedbackContext
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


async def get_beta_player_context(
    request: Request,
    cfg: typing.Annotated[Config, Depends(get_cfg)],
    repo: typing.Annotated[typing.Any, Depends(get_repo)],
    player_id: typing.Annotated[str, Depends(get_player_id)],
) -> PlayerFeedbackContext:
    """Return player id plus email when beta auth supplies one."""
    if not is_auth_required(cfg):
        return PlayerFeedbackContext(player_id=player_id, email=None)
    user = await get_current_user(request, cfg, repo)
    return PlayerFeedbackContext(
        player_id=user.account_id,
        email=user.email,
        plan=user.plan,
        mature_content=user.mature_content,
    )
