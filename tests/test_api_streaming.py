"""Tests for the SSE streaming helpers in ``interfaces.api.streaming``."""

from __future__ import annotations

import json

import allure
import pytest

from interfaces.api.streaming import (
    chunk_text,
    format_sse_event,
    stream_error,
    stream_narration,
)

pytestmark = [
    allure.epic("Player Interfaces"),
    allure.feature("Mobile API"),
]


@allure.story("Chunking")
@allure.title("chunk_text returns an empty list for an empty input string")
def test_chunk_text_empty() -> None:
    assert chunk_text("") == []


@allure.story("Chunking")
@allure.title("chunk_text concatenates back to the original text verbatim")
def test_chunk_text_round_trips_text() -> None:
    text = "The forum stretches before you as dawn breaks over the Palatine Hill."
    chunks = chunk_text(text, words_per_chunk=3)
    assert "".join(chunks) == text


@allure.story("Chunking")
@allure.title("chunk_text rejects a non-positive words_per_chunk")
def test_chunk_text_rejects_invalid_chunk_size() -> None:
    with pytest.raises(ValueError):
        chunk_text("anything", words_per_chunk=0)


@allure.story("SSE framing")
@allure.title("format_sse_event emits event + data lines terminated by a blank line")
def test_format_sse_event_shape() -> None:
    frame = format_sse_event("done", {"narration": "hi", "turn_count": 1})
    assert frame.startswith("event: done\n")
    assert "data: " in frame
    assert frame.endswith("\n\n")
    data_line = next(line for line in frame.splitlines() if line.startswith("data:"))
    assert json.loads(data_line[len("data:") :].strip()) == {"narration": "hi", "turn_count": 1}


@allure.story("SSE framing")
@allure.title("stream_narration yields chunks followed by a single done frame with the final turn_count")
@pytest.mark.asyncio
async def test_stream_narration_emits_chunks_then_done() -> None:
    frames = [frame async for frame in stream_narration("You step forward.", turn_count=4)]
    assert frames, "expected at least one frame"
    done_frame = frames[-1]
    assert done_frame.startswith("event: done\n")
    chunk_frames = frames[:-1]
    assert all(frame.startswith("event: chunk\n") for frame in chunk_frames)


@allure.story("SSE framing")
@allure.title("stream_error yields one error frame carrying the supplied detail message")
@pytest.mark.asyncio
async def test_stream_error_emits_single_error_frame() -> None:
    frames = [frame async for frame in stream_error("nope")]
    assert len(frames) == 1
    assert frames[0].startswith("event: error\n")
    assert '"detail": "nope"' in frames[0]
