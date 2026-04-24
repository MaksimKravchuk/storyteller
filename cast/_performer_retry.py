"""Internal helpers for BasePerformer's prompt-based JSON fallback.

Holds retry bookkeeping and response-cleaning utilities. Lives in its
own module to keep ``cast/base_performer_class.py`` within the flake8
module-member and import budgets.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from llm.message import Message
    from pydantic import BaseModel

_MARKDOWN_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?```\s*$", re.DOTALL)


def _strip_markdown_fence(text: str) -> str:
    """Strip a markdown code fence from an LLM response, returning bare content."""
    stripped = text.strip()
    match = _MARKDOWN_FENCE_RE.match(stripped)
    return match.group(1).strip() if match else stripped


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

    @property
    def total_attempts(self) -> int:
        return self.retries + 1

    @property
    def can_retry(self) -> bool:
        return self.attempt < self.retries
