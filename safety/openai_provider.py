"""Moderation provider backed by OpenAI's ``omni-moderation-latest`` endpoint."""

from __future__ import annotations

import types
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from loguru import logger

from safety.result import ModerationCategory, ModerationSeverity

if TYPE_CHECKING:
    from openai import AsyncOpenAI


_DEFAULT_OPENAI_MODEL = "omni-moderation-latest"

# Buckets are open-on-the-right (``score >= bucket``); anything below the
# LOW threshold is treated as ``NONE`` so we don't churn on noise.
_SCORE_BUCKETS: tuple[tuple[float, ModerationSeverity], ...] = (
    (0.8, ModerationSeverity.HIGH),
    (0.5, ModerationSeverity.MEDIUM),
    (0.2, ModerationSeverity.LOW),
)


_OPENAI_CATEGORY_MAP: Mapping[str, ModerationCategory] = types.MappingProxyType(
    {
        "violence": ModerationCategory.VIOLENCE,
        "violence/graphic": ModerationCategory.VIOLENCE,
        "sexual": ModerationCategory.SEXUAL,
        "sexual/minors": ModerationCategory.SEXUAL_MINORS,
        "harassment": ModerationCategory.HARASSMENT,
        "harassment/threatening": ModerationCategory.HARASSMENT,
        "hate": ModerationCategory.HATE,
        "hate/threatening": ModerationCategory.HATE,
        "self-harm": ModerationCategory.SELF_HARM,
        "self-harm/intent": ModerationCategory.SELF_HARM,
        "self-harm/instructions": ModerationCategory.SELF_HARM,
        "illicit": ModerationCategory.ILLICIT,
        "illicit/violent": ModerationCategory.ILLICIT,
    },
)


def _resolve_openai_error_types() -> tuple[type[BaseException], ...]:
    """Narrow tuple of OpenAI / transport errors to catch.

    Resolved once at import time and cached on :data:`_OPENAI_ERROR_TYPES`.
    Falls back to plain transport errors when ``openai`` isn't importable
    so the moderator never accidentally swallows ``CancelledError`` or
    SDK contract violations.
    """
    try:
        from openai import APIError, APIConnectionError, APIStatusError, APITimeoutError, RateLimitError
    except ImportError:
        return (ConnectionError, OSError, TimeoutError)
    return (APIError, APIConnectionError, APIStatusError, APITimeoutError, RateLimitError)


_OPENAI_ERROR_TYPES: tuple[type[BaseException], ...] = _resolve_openai_error_types()


class ModerationProviderError(RuntimeError):
    """Raised when an upstream moderation provider call fails."""


@dataclass
class OpenAIModerationProvider:
    """Provider backed by OpenAI's ``omni-moderation-latest`` endpoint.

    Lazily instantiates the ``AsyncOpenAI`` client so the ``openai``
    package remains an optional dependency. Network and API errors
    surface as :class:`ModerationProviderError` so callers can decide
    whether to fail-open or fail-closed.
    """

    api_key: str | None = None
    model: str = _DEFAULT_OPENAI_MODEL
    name: str = "openai"
    _client: Any = field(default=None, init=False, repr=False)

    async def score(self, text: str) -> Mapping[ModerationCategory, ModerationSeverity]:
        if not text.strip():
            return {}
        client = self._get_client()
        try:
            response = await client.moderations.create(model=self.model, input=text)
        except _OPENAI_ERROR_TYPES as exc:
            logger.warning(
                "content_safety.openai_error type={} message={}",
                type(exc).__name__,
                exc,
            )
            # Generic wrap so request URLs / payloads / headers from
            # ``str(exc)`` never reach a FastAPI 500 detail or chat reply.
            raise ModerationProviderError("openai moderation request failed") from exc
        return severities_from_response(response)

    def _get_client(self) -> "AsyncOpenAI":
        if self._client is None:
            from openai import AsyncOpenAI

            kwargs: dict[str, Any] = {}
            if self.api_key is not None:
                kwargs["api_key"] = self.api_key
            self._client = AsyncOpenAI(**kwargs)
        return self._client


def score_to_severity(score: float) -> ModerationSeverity:
    """Map a 0–1 score from the OpenAI moderation endpoint to a severity bucket."""
    for bucket_threshold, bucket_severity in _SCORE_BUCKETS:
        if score >= bucket_threshold:
            return bucket_severity
    return ModerationSeverity.NONE


def severities_from_response(response: Any) -> Mapping[ModerationCategory, ModerationSeverity]:
    """Translate an OpenAI moderation response into category→severity buckets.

    Robust to both pydantic models (``response.results[0].category_scores.violence``)
    and plain-dict shapes (``response["results"][0]["category_scores"]``).
    Unknown wire categories are ignored — additions to OpenAI's taxonomy
    won't cause crashes, but they also won't be enforced until the local
    map gains an entry.
    """
    severities: dict[ModerationCategory, ModerationSeverity] = {}
    for wire_key, raw_score in _extract_category_scores(response).items():
        category = _OPENAI_CATEGORY_MAP.get(wire_key)
        if category is None:
            continue
        severity = score_to_severity(float(raw_score))
        if severity > severities.get(category, ModerationSeverity.NONE):
            severities[category] = severity
    return severities


def _extract_category_scores(response: Any) -> Mapping[str, float]:
    """Return ``response.results[0].category_scores`` across all wire shapes.

    Handles both the pydantic-model shape returned by the OpenAI SDK and
    the plain-dict shape used by tests / replayed fixtures. Returns an
    empty mapping when ``results`` is missing/empty so the caller never
    has to special-case the ``no results`` path.
    """
    container = getattr(response, "results", None)
    if container is None and isinstance(response, dict):
        container = response.get("results")
    if not container:
        return {}
    return _category_scores_from_payload(container[0])


def _category_scores_from_payload(payload: Any) -> Mapping[str, float]:
    """Pull ``category_scores`` off a single ``results[0]`` payload."""
    if isinstance(payload, dict):
        return payload.get("category_scores", {})
    scores = getattr(payload, "category_scores", None)
    if scores is None:
        return {}
    if isinstance(scores, dict):
        return scores
    if hasattr(scores, "model_dump"):
        # The SDK's Python field names are ``sexual_minors``; the map keys are the wire names.
        return scores.model_dump(by_alias=True)
    return dict(scores.__dict__)
