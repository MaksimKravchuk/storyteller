"""Image generation for optional story-poster illustrations (ADR-0019).

Kept apart from the chat-completion clients: posters are the only image
call, they are paid per image, and they only run on an explicit player
request. The OpenAI SDK is imported lazily like ``llm.openai_client``.
"""

from __future__ import annotations

import base64
import time
from dataclasses import dataclass
from typing import Any, Protocol

_POSTER_SIZE = "1024x1536"
_OUTPUT_FORMAT = "webp"
_OUTPUT_COMPRESSION = 82
_WEBP_MIME = "image/webp"
_MS_PER_SECOND = 1000


@dataclass(frozen=True)
class GeneratedImage:
    """One generated image plus the usage needed for cost telemetry."""

    image_bytes: bytes
    mime: str
    model: str
    input_tokens: int | None
    output_tokens: int | None
    duration_ms: int


class ImageClient(Protocol):
    """Anything that turns a prompt into a :class:`GeneratedImage`."""

    async def generate(self, prompt: str) -> GeneratedImage:
        """Generate one portrait poster image for ``prompt``."""


def _usage_tokens(usage: Any, field: str) -> int | None:
    token_count = getattr(usage, field, None)
    if token_count is None:
        return None
    return int(token_count)


class OpenAIImageClient:
    """Portrait poster images from an OpenAI ``gpt-image`` model."""

    def __init__(self, api_key: str, model: str, quality: str) -> None:
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(api_key=api_key)
        self._model = model
        self._quality = quality

    async def generate(self, prompt: str) -> GeneratedImage:
        """Generate one portrait WebP poster for ``prompt``."""
        started = time.monotonic()
        response = await self._client.images.generate(
            model=self._model,
            prompt=prompt,
            size=_POSTER_SIZE,
            quality=self._quality,
            output_format=_OUTPUT_FORMAT,
            output_compression=_OUTPUT_COMPRESSION,
            n=1,
        )
        encoded = response.data[0].b64_json if response.data else None
        if not encoded:
            raise ValueError("image model returned no image data")
        return GeneratedImage(
            image_bytes=base64.b64decode(encoded),
            mime=_WEBP_MIME,
            model=self._model,
            input_tokens=_usage_tokens(response.usage, "input_tokens"),
            output_tokens=_usage_tokens(response.usage, "output_tokens"),
            duration_ms=int((time.monotonic() - started) * _MS_PER_SECOND),
        )
