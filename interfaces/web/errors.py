"""Web-layer exceptions and provider-error classification helpers."""

from __future__ import annotations


class GameNotFoundError(Exception):
    """Raised when a web player has no active game or unknown game_id."""


class GameStartUnavailableError(Exception):
    """Raised when provider/configuration problems make game start unavailable."""


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
