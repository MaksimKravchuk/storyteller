"""Business logic for in-app beta feedback."""

from __future__ import annotations

from dataclasses import dataclass

from config import Config
from db.repository import GameRepository
from interfaces.web import beta_policy
from interfaces.web.service_helpers import owned_session_context

BetaAccessDeniedError = beta_policy.BetaAccessDeniedError


@dataclass(frozen=True)
class FeedbackSubmission:
    """Bundle of fields needed to persist one beta feedback item."""

    player_id: str
    email: str | None
    game_id: str
    category: str
    message: str


async def submit_beta_feedback(repo: GameRepository, cfg: Config, submission: FeedbackSubmission) -> str:
    """Store feedback for a game only after proving caller ownership."""
    policy = beta_policy.BetaPolicy(repo, cfg)
    await policy.ensure_open()
    await owned_session_context(repo, submission.player_id, submission.game_id)
    feedback_id = await repo.feedback.create(
        submission.player_id,
        submission.email,
        submission.game_id,
        submission.category,
        submission.message,
    )
    await repo.commit()
    return feedback_id
