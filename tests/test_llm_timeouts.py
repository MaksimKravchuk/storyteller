"""Every provider SDK client is built with a bounded timeout.

SDK defaults are a 600 s read timeout with 2 retries; layered under the
app's own retries one hung upstream call could hold a turn (and the
player's lock) for over an hour.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import allure
import httpx
import pytest
from openai import RateLimitError

from llm.anthropic_client import AnthropicClient
from llm.image_client import OpenAIImageClient
from llm.openai_client import OpenAIClient, _call_with_retry
from safety.openai_provider import OpenAIModerationProvider

pytestmark = [
    allure.epic("Engine & LLM Infrastructure"),
    allure.feature("LLM clients"),
    allure.story("Timeouts and retries"),
]


@allure.title("OpenAI chat client times out at 120 s and leaves retries to the app's single retry layer")
def test_openai_chat_client_timeout() -> None:
    sdk = OpenAIClient(api_key="k")._client
    assert sdk.timeout == 120
    assert sdk.max_retries == 0


@allure.title("Anthropic, image and moderation clients carry bounded timeouts")
def test_other_client_timeouts() -> None:
    assert AnthropicClient(api_key="k")._client.timeout == 120
    assert OpenAIImageClient(api_key="k", model="gpt-image", quality="low")._client.timeout == 180
    assert OpenAIModerationProvider(api_key="k")._get_client().timeout == 15


@allure.title("With SDK retries off, the app retry layer still retries a 429 rate limit")
@pytest.mark.asyncio
async def test_app_retry_covers_rate_limit() -> None:
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    rate_limited = RateLimitError("slow down", response=httpx.Response(429, request=request), body=None)
    create = AsyncMock(side_effect=[rate_limited, "ok"])
    with patch("llm.retry.asyncio.sleep", new=AsyncMock()):
        assert await _call_with_retry(create) == "ok"
    assert create.await_count == 2


@allure.title("A 429 with Retry-After waits the server-directed cooldown (capped at 60 s) before retrying")
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("headers", "expected_delay"), [({"retry-after": "10"}, 10), ({"retry-after-ms": "900000"}, 60)]
)
async def test_app_retry_honors_retry_after(headers: dict[str, str], expected_delay: float) -> None:
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    response = httpx.Response(429, request=request, headers=headers)
    create = AsyncMock(side_effect=[RateLimitError("slow down", response=response, body=None), "ok"])
    sleep = AsyncMock()
    with patch("llm.retry.asyncio.sleep", new=sleep):
        assert await _call_with_retry(create) == "ok"
    sleep.assert_awaited_once_with(expected_delay)
