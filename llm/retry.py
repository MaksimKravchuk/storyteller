"""One bounded-backoff retry loop shared by the OpenAI and Anthropic clients.

Both SDKs run with ``max_retries=0`` so retries live here only, are counted in
the reliability metrics, and never multiply with SDK-internal retries.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from loguru import logger

_MAX_ATTEMPTS = 3
_BASE_DELAY = 2.0
# Same ceiling the SDKs applied to server-directed ``Retry-After`` delays.
_MAX_SERVER_DELAY_S = 60.0


def server_delay(exc: Exception) -> float:
    """Return the response's ``retry-after-ms`` / ``retry-after`` seconds, capped; 0 when absent or unparsable."""
    response = getattr(exc, "response", None)
    if response is None:
        return 0
    retry_after_ms = response.headers.get("retry-after-ms")
    try:
        if retry_after_ms is None:
            seconds = float(response.headers.get("retry-after", 0))
        else:
            seconds = float(retry_after_ms) / 1000
    except ValueError:  # HTTP-date form: fall back to our own backoff
        return 0
    return min(max(seconds, 0), _MAX_SERVER_DELAY_S)


async def call_with_retry(
    create: Callable[[], Awaitable[Any]],
    retry_on: tuple[type[Exception], ...],
    agent: str,
    attempt: int = 0,
) -> Any:
    """Invoke ``create`` with bounded exponential backoff on the ``retry_on`` exceptions.

    Backoff is ``2s * 2**attempt``, or the server's ``Retry-After`` when
    longer (capped at 60 s). Other errors (4xx, validation) propagate
    immediately. Each retry is recorded under ``agent`` in the reliability
    metrics. Implemented via tail recursion so the retry loop carries its own
    attempt counter without an ``await`` inside a ``for`` loop body.
    """
    from cast import _reliability_metrics

    try:
        return await create()
    except retry_on as exc:
        if attempt + 1 >= _MAX_ATTEMPTS:
            raise
        delay = max(_BASE_DELAY * (2**attempt), server_delay(exc))
        _reliability_metrics.record_retry(agent, attempt + 1)
        logger.warning(
            "{} transient error (attempt {}/{}); retrying in {}s: {}",
            agent,
            attempt + 1,
            _MAX_ATTEMPTS,
            delay,
            exc,
        )
        await asyncio.sleep(delay)
    return await call_with_retry(create, retry_on, agent, attempt + 1)
