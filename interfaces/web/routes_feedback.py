"""FastAPI routes for in-app beta feedback."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from config import Config
from db.repository import GameRepository
from interfaces.web import deps, schemas_feedback, service, service_feedback
from interfaces.web.auth_models import PlayerFeedbackContext
from interfaces.web.beta_auth import get_beta_player_context

router = APIRouter()

FeedbackCtxDep = Annotated[PlayerFeedbackContext, Depends(get_beta_player_context)]
CfgDep = Annotated[Config, Depends(deps.get_cfg)]
RepoDep = Annotated[GameRepository, Depends(deps.get_repo)]

_NO_ACTIVE_GAME_DETAIL = "No active game"


@router.post(
    "/api/games/{game_id}/feedback",
    response_model=schemas_feedback.FeedbackResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def post_feedback(
    game_id: str,
    body: schemas_feedback.FeedbackRequest,
    player: FeedbackCtxDep,
    cfg: CfgDep,
    repo: RepoDep,
) -> schemas_feedback.FeedbackResponse:
    """Submit in-app beta feedback tied to the caller's owned game."""
    try:
        feedback_id = await service_feedback.submit_beta_feedback(
            repo,
            cfg,
            service_feedback.FeedbackSubmission(
                player_id=player.player_id,
                email=player.email,
                game_id=game_id,
                category=body.category,
                message=body.message,
            ),
        )
    except service_feedback.BetaAccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=exc.message) from exc
    except service.GameNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NO_ACTIVE_GAME_DETAIL) from exc
    return schemas_feedback.FeedbackResponse(feedback_id=feedback_id)
