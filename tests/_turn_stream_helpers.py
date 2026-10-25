"""Shared fakes for live turn-stream tests."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from starlette.types import Message


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
