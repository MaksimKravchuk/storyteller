"""Shared fakes for live turn-stream tests."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RecordingSink:
    """Turn-stream sink that records every event."""

    stages: list[str] = field(default_factory=list)
    deltas: list[str] = field(default_factory=list)

    async def stage(self, name: str) -> None:
        self.stages.append(name)

    async def delta(self, text: str) -> None:
        self.deltas.append(text)
