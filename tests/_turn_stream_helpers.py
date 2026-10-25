"""Shared fakes for live turn-stream tests."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Mapping
from dataclasses import dataclass, field

from starlette.types import Message

from safety.result import ModerationCategory, ModerationSeverity

_IDLE_WAIT_S = 0.01


@dataclass
class RecordingSink:
    """Turn-stream sink that records every event."""

    stages: list[str] = field(default_factory=list)
    deltas: list[str] = field(default_factory=list)

    async def stage(self, name: str) -> None:
        self.stages.append(name)

    async def delta(self, text: str) -> None:
        self.deltas.append(text)


class VanishedClient:
    """ASGI peer that drops off while a body frame is being sent, so that send never completes."""

    def __init__(self) -> None:
        self.stalled = asyncio.Event()

    async def send(self, message: Message) -> None:
        if message["type"] == "http.response.body":
            self.stalled.set()
            await asyncio.Event().wait()

    async def receive(self) -> Message:
        await self.stalled.wait()
        return {"type": "http.disconnect"}


@dataclass
class HeldProvider:
    """Moderation provider that records each check, then waits for ``release`` before passing it."""

    name: str = "held"
    seen: list[str] = field(default_factory=list)
    release: asyncio.Event = field(default_factory=asyncio.Event)

    async def score(self, text: str) -> Mapping[ModerationCategory, ModerationSeverity]:
        self.seen.append(text)
        await self.release.wait()
        return {}


async def bounded(step: Awaitable[None]) -> None:
    """Await ``step``, failing instead of hanging if it never completes."""
    await asyncio.wait_for(step, timeout=1)


async def settle() -> None:
    """Let every queued task run until the loop goes idle."""
    await asyncio.sleep(_IDLE_WAIT_S)
