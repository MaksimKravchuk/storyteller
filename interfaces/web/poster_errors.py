"""Refusals from the poster illustration service; each carries its HTTP answer."""

from __future__ import annotations

_HTTP_NOT_FOUND = 404
_HTTP_CONFLICT = 409
_HTTP_TOO_MANY_REQUESTS = 429
_HTTP_SERVICE_UNAVAILABLE = 503
_NO_POSTER_DETAIL = "No poster for this story"


class PosterError(RuntimeError):
    """Base class for poster refusals; the route answers ``status_code`` / ``detail``."""

    status_code = _HTTP_NOT_FOUND
    detail = _NO_POSTER_DETAIL


class PosterUnavailableError(PosterError):
    """Illustrations are switched off or no image provider is configured."""


class PosterMissingError(PosterError):
    """The story has no playbill to illustrate."""


class PosterExistsError(PosterError):
    """The story already has its one illustration."""

    status_code = _HTTP_CONFLICT
    detail = "This story already has its poster."


class PosterQuotaError(PosterError):
    """The player used up today's illustrations."""

    status_code = _HTTP_TOO_MANY_REQUESTS
    detail = "You have painted today's posters. Try again tomorrow."


class PosterFailedError(PosterError):
    """The image provider failed to produce an image."""

    status_code = _HTTP_SERVICE_UNAVAILABLE
    detail = "The painter could not finish this poster. Please try again later."
