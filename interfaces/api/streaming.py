"""Server-Sent Events helpers for the mobile API.

The engine returns the full narration string from
``GameEngine.process_action``; we don't have token-level streaming
inside the engine itself. To still give native clients an
incremental rendering experience, we chunk the finished narration on
whitespace and emit each chunk as an ``event: chunk`` SSE frame,
followed by a final ``event: done`` frame carrying the new
``turn_count`` and the full narration text. Clients that don't care
about chunks can wait for ``done`` and use ``narration`` directly.
"""

from __future__ import annotations

import json
from typing import AsyncIterator

_CHUNK_WORDS = 8  # ~one short phrase per frame; deliberately small for visible streaming


def chunk_text(text: str, words_per_chunk: int = _CHUNK_WORDS) -> list[str]:
    """Split ``text`` into whitespace-aligned chunks of ``words_per_chunk`` words.

    Preserves the input verbatim when chunks are concatenated.
    """
    if not text:
        return []
    if words_per_chunk < 1:
        raise ValueError("words_per_chunk must be at least 1")
    parts = text.split(" ")
    chunks: list[str] = []
    for start in range(0, len(parts), words_per_chunk):
        group = parts[start : start + words_per_chunk]
        chunk = " ".join(group)
        if start + words_per_chunk < len(parts):
            chunk = "{0} ".format(chunk)
        chunks.append(chunk)
    return chunks


def format_sse_event(event: str, payload: dict) -> str:
    """Encode one Server-Sent Events frame."""
    return "event: {0}\ndata: {1}\n\n".format(event, json.dumps(payload, ensure_ascii=False))


async def stream_narration(narration: str, turn_count: int) -> AsyncIterator[str]:
    """Yield SSE frames for a completed narration string.

    Emits one ``chunk`` event per whitespace-aligned slice and a final
    ``done`` event carrying the full narration and new ``turn_count``.
    """
    for chunk in chunk_text(narration):
        yield format_sse_event("chunk", {"text": chunk})
    yield format_sse_event("done", {"narration": narration, "turn_count": turn_count})


async def stream_error(message: str) -> AsyncIterator[str]:
    """Yield a single ``error`` SSE frame."""
    yield format_sse_event("error", {"detail": message})
