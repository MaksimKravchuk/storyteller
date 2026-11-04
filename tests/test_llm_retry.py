"""Shared LLM retry loop: Anthropic 429 is retried by us (SDK retries off) and counted in reliability metrics."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import allure
import httpx
import pytest
from anthropic import RateLimitError

from cast import _reliability_metrics
from llm.anthropic_client import _call_with_retry

pytestmark = [allure.epic("LLM"), allure.feature("Retry")]


@allure.story("Retry on 429")
@allure.title("Anthropic call_with_retry retries 429 and records the retry metric")
@pytest.mark.asyncio
async def test_anthropic_retries_rate_limit_and_records_metric() -> None:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    rate_limited = RateLimitError("slow down", response=httpx.Response(429, request=request), body=None)
    create = AsyncMock(side_effect=[rate_limited, "ok"])
    _reliability_metrics.reset_counters()

    with patch("llm.retry.asyncio.sleep", new=AsyncMock()):
        assert await _call_with_retry(create) == "ok"

    assert _reliability_metrics.snapshot_counters()[("anthropic_client", "validation_retry")] == 1
