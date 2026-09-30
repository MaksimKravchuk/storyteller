"""Tests for the poster image client (``llm.image_client``)."""

from __future__ import annotations

import base64
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import allure
import pytest

from llm.image_client import OpenAIImageClient

pytestmark = [
    allure.epic("Engine & LLM Infrastructure"),
    allure.feature("LLM clients"),
]

_STORY = "Image client"


def _openai_with(response: object) -> MagicMock:
    sdk_client = MagicMock()
    sdk_client.images.generate = AsyncMock(return_value=response)
    return sdk_client


@pytest.mark.asyncio
@allure.story(_STORY)
@allure.title("OpenAIImageClient asks for one portrait WebP and returns decoded bytes with token usage")
async def test_generate_decodes_image_and_usage() -> None:
    encoded = base64.b64encode(b"RIFF-webp").decode()
    usage = SimpleNamespace(input_tokens=120, output_tokens=4160)
    sdk_client = _openai_with(SimpleNamespace(data=[SimpleNamespace(b64_json=encoded)], usage=usage))

    with patch("openai.AsyncOpenAI", return_value=sdk_client):
        image = await OpenAIImageClient(api_key="sk-test", model="gpt-image-1-mini", quality="medium").generate("p")

    assert (image.image_bytes, image.mime, image.model) == (b"RIFF-webp", "image/webp", "gpt-image-1-mini")
    assert (image.input_tokens, image.output_tokens) == (120, 4160)
    call = sdk_client.images.generate.await_args.kwargs
    assert (call["size"], call["output_format"], call["quality"], call["n"]) == ("1024x1536", "webp", "medium", 1)


@pytest.mark.asyncio
@allure.story(_STORY)
@allure.title("OpenAIImageClient reports missing usage as None so spend reports flag it")
async def test_generate_without_usage() -> None:
    encoded = base64.b64encode(b"x").decode()
    sdk_client = _openai_with(SimpleNamespace(data=[SimpleNamespace(b64_json=encoded)], usage=None))

    with patch("openai.AsyncOpenAI", return_value=sdk_client):
        image = await OpenAIImageClient(api_key="sk-test", model="m", quality="low").generate("p")

    assert (image.input_tokens, image.output_tokens) == (None, None)


@pytest.mark.asyncio
@allure.story(_STORY)
@allure.title("OpenAIImageClient raises when the provider returns no image")
async def test_generate_without_image_raises() -> None:
    sdk_client = _openai_with(SimpleNamespace(data=[], usage=None))

    with patch("openai.AsyncOpenAI", return_value=sdk_client), pytest.raises(ValueError, match="no image data"):
        await OpenAIImageClient(api_key="sk-test", model="m", quality="low").generate("p")
