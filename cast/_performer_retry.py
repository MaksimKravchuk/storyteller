"""Internal helpers for BasePerformer's prompt-based JSON fallback.

Holds retry bookkeeping and response-cleaning utilities. Lives in its
own module to keep ``cast/base_performer_class.py`` within the flake8
module-member and import budgets.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from cast._reliability_metrics import record_retry
from llm.base_client import LLMJSONError
from pydantic import ValidationError

if TYPE_CHECKING:
    from llm.message import Message
    from pydantic import BaseModel

_MARKDOWN_FENCE_RE = re.compile(r"^```[a-zA-Z]*\s*\n?(.*?)\n?```", re.DOTALL)


def strict_json_decode_error(raw: str, exc: Exception) -> LLMJSONError:
    """Build a consistent strict structured-output validation error."""
    return LLMJSONError(
        "Strict structured output failed validation: {0}".format(exc),
        raw_response=raw,
    )


def validate_strict_json(raw: str, response_model: type["BaseModel"]):
    """Decode and validate strict JSON, preserving schema failures as LLMJSONError."""
    payload = json.loads(raw)
    try:
        return response_model.model_validate(payload)
    except ValidationError as exc:
        raise strict_json_decode_error(raw, exc) from exc


def validate_strict_retry_json(raw: str, response_model: type["BaseModel"]):
    """Validate retry payload and wrap malformed JSON as LLMJSONError."""
    try:
        return validate_strict_json(raw, response_model)
    except json.JSONDecodeError as exc:
        raise strict_json_decode_error(raw, exc) from exc


def _strip_markdown_fence(text: str) -> str:
    """Strip a markdown code fence from an LLM response, returning bare content."""
    stripped = text.strip()
    match = _MARKDOWN_FENCE_RE.match(stripped)
    return match.group(1).strip() if match else stripped


def record_validation_retry(agent_name: str, attempt: int) -> None:
    """Bookkeep one validation retry against the per-turn reliability counters.

    Lives here so ``base_performer_class`` does not need a direct
    ``_reliability_metrics`` import (keeps that module's import budget
    inside its WPS201 limit). Phase 1 is metering-only: the recorder
    is a no-op when no turn-scoped buffer is bound.
    """
    record_retry(agent_name, attempt)


@dataclass(frozen=True)
class RetryContext:
    """Parameters shared between attempts of the ``_send_json`` retry loop.

    Bundles the recursion state so the retry helpers don't need to take
    eight positional arguments each.
    """

    user_message: str
    conversation: list["Message"] | None
    retries: int
    attempt: int
    response_model: type["BaseModel"] | None
    max_tokens: int | None = None
