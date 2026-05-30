"""Translate player-action service errors into HTTP responses.

Split out of ``routes.py`` so the ``post_action`` handler stays a single
``except`` clause (wemake caps except cases / raises per function) while the
per-error status mapping lives in one place.
"""

from __future__ import annotations

from fastapi import HTTPException, status

from interfaces.web.beta_policy import BetaAccessDeniedError
from interfaces.web.errors import GameNotFoundError, GameStartUnavailableError
from safety.moderator import SafetyRejectedError

_NO_ACTIVE_GAME_DETAIL = "No active game"
_START_UNAVAILABLE_DETAIL = "Storyteller is temporarily unable to start games. Please try again later."
_HTTP_TOO_MANY_REQUESTS = 429

# Service-layer exceptions ``post_action`` knows how to translate to HTTP.
ACTION_ERRORS = (BetaAccessDeniedError, GameNotFoundError, GameStartUnavailableError, SafetyRejectedError)


def to_http_exception(exc: Exception) -> HTTPException:
    """Map a player-action service error to its HTTP response."""
    if isinstance(exc, BetaAccessDeniedError):
        hard_stop = exc.reason in {"beta_disabled", "global_budget_exhausted"}
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE if hard_stop else _HTTP_TOO_MANY_REQUESTS
        return HTTPException(status_code=status_code, detail=exc.message)
    if isinstance(exc, GameNotFoundError):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NO_ACTIVE_GAME_DETAIL)
    if isinstance(exc, GameStartUnavailableError):
        return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=_START_UNAVAILABLE_DETAIL)
    if isinstance(exc, SafetyRejectedError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.refusal_message)
    raise exc
