"""Web-layer exceptions and provider-error classification helpers."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from loguru import logger
from sqlalchemy.exc import SQLAlchemyError

_ACCOUNT_STORE_UNAVAILABLE_DETAIL = "Account service temporarily unavailable"


async def guard_account_query(operation: Any, *args: Any) -> Any:
    """Await an account-store DB call, mapping DB faults to a retryable 503.

    A transient DB error in the shared auth dependency (a poisoned pooled
    connection, a brief Postgres blip) would otherwise bubble up as a raw 500
    with a full diagnostic traceback and block every authenticated request.
    Surface it as a clean 503 the client can retry — logged first so the
    failure stays visible to operators rather than vanishing silently.
    """
    try:
        return await operation(*args)
    except SQLAlchemyError as exc:
        logger.warning("Account-store query failed in auth gate: {}", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_ACCOUNT_STORE_UNAVAILABLE_DETAIL,
        ) from exc


class GameNotFoundError(Exception):
    """Raised when a web player has no active game or unknown game_id."""


class GameStartUnavailableError(Exception):
    """Raised when provider/configuration problems make game start unavailable."""


class GameStartFailedError(Exception):
    """Raised when runtime game-start failures should be reported safely to players."""


def is_provider_auth_error(exc: Exception) -> bool:
    """Return True for common LLM provider credential/authentication failures."""
    exc_type_names = {type(exc).__name__}
    exc_type_names.update(base.__name__ for base in type(exc).__mro__)
    if any("AuthenticationError" in name or "PermissionDeniedError" in name for name in exc_type_names):
        return True

    message = str(exc).lower()
    return any(
        marker in message
        for marker in (
            "invalid_api_key",
            "invalid api key",
            "invalid x-api-key",
            "incorrect api key",
            "authentication",
            "unauthorized",
        )
    )
