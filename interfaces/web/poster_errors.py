"""Refusals from the poster illustration service, mapped to HTTP by the route."""

from __future__ import annotations


class PosterError(RuntimeError):
    """Base class for poster illustration refusals."""


class PosterUnavailableError(PosterError):
    """Illustrations are switched off or no image provider is configured."""


class PosterMissingError(PosterError):
    """The story has no playbill to illustrate."""


class PosterExistsError(PosterError):
    """The story already has its one illustration."""


class PosterQuotaError(PosterError):
    """The player used up today's illustrations."""


class PosterRejectedError(PosterError):
    """Moderation flagged the illustration prompt."""


class PosterFailedError(PosterError):
    """The image provider failed to produce an image."""
