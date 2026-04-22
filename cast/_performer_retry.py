"""Retry bookkeeping for BasePerformer's prompt-based JSON fallback.

Lives in its own module to keep ``cast/base_performer_class.py`` within
the flake8 module-member budget.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from llm.message import Message
    from pydantic import BaseModel


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
