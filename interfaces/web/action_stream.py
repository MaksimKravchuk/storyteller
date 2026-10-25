"""Server-sent-event response for one player turn.

The turn runs in its own task and pushes ``stage`` / ``delta`` events
through a queue; the response body drains that queue as SSE frames and
ends with exactly one ``done`` (the full ``ActionResponse``) or ``error``
(the HTTP status + detail the non-streamed route would have returned).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from typing import AsyncGenerator, Awaitable, Callable

import anyio
from fastapi.responses import StreamingResponse
from loguru import logger
from starlette.types import Receive, Scope, Send

from interfaces.web import action_errors
from interfaces.web.schemas import ActionResponse
from llm import turn_stream

_HTTP_INTERNAL_SERVER_ERROR = 500
_TURN_FAILED_DETAIL = "The story stumbled on this turn. Please try again."

_Event = tuple[str, dict[str, object]]
TurnRunner = Callable[[], Awaitable[ActionResponse]]


class _QueueSink:
    """Turn-stream sink that enqueues events for the response body."""

    def __init__(self, queue: asyncio.Queue[_Event | None]) -> None:
        self._queue = queue

    async def stage(self, name: str) -> None:
        await self._queue.put(("stage", {"stage": name}))

    async def delta(self, text: str) -> None:
        await self._queue.put(("delta", {"text": text}))


def _sse_frame(event: _Event) -> str:
    """Encode one event as an SSE frame."""
    name, payload = event
    return "event: {0}\ndata: {1}\n\n".format(name, json.dumps(payload, ensure_ascii=False))


async def _run_to_queue(run_turn: TurnRunner, queue: asyncio.Queue[_Event | None]) -> None:
    """Run the turn, then enqueue its terminal event and the end-of-stream marker."""
    try:
        with turn_stream.bound(_QueueSink(queue)):
            response = await run_turn()
    except action_errors.ACTION_ERRORS as exc:
        http_error = action_errors.to_http_exception(exc)
        await queue.put(("error", {"status": http_error.status_code, "detail": http_error.detail}))
    except Exception:
        logger.exception("Streamed player turn failed")
        await queue.put(("error", {"status": _HTTP_INTERNAL_SERVER_ERROR, "detail": _TURN_FAILED_DETAIL}))
    else:
        await queue.put(("done", response.model_dump(mode="json")))
    finally:
        await queue.put(None)


async def _finish_shielded(turn: asyncio.Task[None]) -> None:
    """Wait for the turn even while the response is being cancelled.

    A dropped connection must not abandon a paid turn: it finishes and
    persists, which also keeps the request-scoped DB session open until then.
    """
    with anyio.CancelScope(shield=True):
        await turn


async def _drain(queue: asyncio.Queue[_Event | None]) -> AsyncGenerator[str, None]:
    """Yield queued events as SSE frames until the end-of-stream marker."""
    event = await queue.get()
    while event is not None:
        yield _sse_frame(event)
        event = await queue.get()


class TurnStreamResponse(StreamingResponse):
    """SSE response that owns the turn task and never returns before the turn ends.

    The wait lives here, not in the body generator: a disconnect while a frame
    is being sent cancels the send and leaves the generator suspended, but this
    call still blocks request teardown (and the DB session) until the turn is done.
    """

    def __init__(self, run_turn: TurnRunner) -> None:
        self._queue: asyncio.Queue[_Event | None] = asyncio.Queue()
        self._run_turn = run_turn
        super().__init__(
            _drain(self._queue),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        async with contextlib.AsyncExitStack() as cleanup:
            turn = asyncio.create_task(_run_to_queue(self._run_turn, self._queue))
            cleanup.push_async_callback(_finish_shielded, turn)
            await super().__call__(scope, receive, send)
