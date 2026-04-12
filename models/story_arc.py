"""StoryArc and supporting dataclasses for narrative pacing.

Pure data plumbing for the upcoming Playwright agent. ``StoryArc``
tracks the current act, the active beat, the ordered list of beats
that have been planned so far, and the open plot threads. No agent
reads or writes any of these fields yet.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from models.base_model import BaseModel

BeatKind = Literal["setup", "rising", "climax", "falling", "resolution"]
ThreadStatus = Literal["open", "resolved", "abandoned"]


@dataclass(kw_only=True)
class Beat(BaseModel):
    """A single narrative beat planned by the Playwright."""

    description: str
    kind: BeatKind
    resolved: bool = False


@dataclass(kw_only=True)
class PlotThread(BaseModel):
    """A long-running plot thread the Playwright is keeping alive."""

    description: str
    introduced_scene: int
    involved_npcs: list[str] = field(default_factory=list)
    status: ThreadStatus = "open"


@dataclass(kw_only=True)
class StoryArc(BaseModel):
    """Top-level narrative arc for a game session."""

    act: int = 1
    current_beat_id: str | None = None
    beats: list[Beat] = field(default_factory=list)
    threads: list[PlotThread] = field(default_factory=list)
