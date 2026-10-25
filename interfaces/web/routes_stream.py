"""Streamed player-turn route (server-sent events)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from config import Config
from db.repository import GameRepository
from interfaces.web import action_stream, deps, schemas, service
from interfaces.web.auth_models import PlayerFeedbackContext
from interfaces.web.beta_auth import get_beta_player_context

router = APIRouter()

PlayerCtxDep = Annotated[PlayerFeedbackContext, Depends(get_beta_player_context)]
CfgDep = Annotated[Config, Depends(deps.get_cfg)]
RepoDep = Annotated[GameRepository, Depends(deps.get_repo)]


@router.post("/api/games/{game_id}/actions/stream", response_class=StreamingResponse)
async def post_action_stream(
    game_id: str,
    body: schemas.ActionRequest,
    player: PlayerCtxDep,
    cfg: CfgDep,
    repo: RepoDep,
) -> StreamingResponse:
    """Submit a player action and stream its progress as server-sent events.

    Emits ``stage`` and ``delta`` (Narrator prose) events, then one ``done``
    carrying the same ``ActionResponse`` as ``POST .../actions``, or one
    ``error`` carrying the status and detail that route would have returned.
    """
    return action_stream.TurnStreamResponse(
        lambda: service.process_turn_for_player(repo, cfg, player, game_id, body),
    )
