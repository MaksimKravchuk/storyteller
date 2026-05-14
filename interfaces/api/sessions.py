"""In-memory session store for the mobile HTTP/SSE API.

A session bundles a live ``GameEngine`` with the metadata needed to
serialise it to the wire (setting, language, transcript, timestamps).
Each session carries its own ``asyncio.Lock`` so concurrent action
requests against the same session are serialised — the engine itself
is not safe to drive in parallel.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from engine.game_engine import GameEngine


@dataclass
class SessionEntry:
    """One live game session held in memory."""

    session_id: str
    engine: GameEngine
    setting: str
    language: str
    opening_scene: str
    created_at: datetime
    transcript: list[dict] = field(default_factory=list)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def add_turn(self, role: str, text: str) -> None:
        """Append a transcript entry."""
        self.transcript.append({"role": role, "text": text})


class SessionStore:
    """Process-local store of live game sessions.

    Not durable — sessions disappear on process restart. Intended for
    short-lived mobile clients; persistence belongs in the database-backed
    ``interfaces.web`` flow.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, SessionEntry] = {}

    def create(
        self,
        *,
        engine: GameEngine,
        setting: str,
        language: str,
        opening_scene: str,
    ) -> SessionEntry:
        """Register a freshly-started engine as a new session."""
        session_id = str(uuid4())
        entry = SessionEntry(
            session_id=session_id,
            engine=engine,
            setting=setting,
            language=language,
            opening_scene=opening_scene,
            created_at=datetime.now(timezone.utc),
        )
        entry.add_turn("narrator", opening_scene)
        self._sessions[session_id] = entry
        return entry

    def get(self, session_id: str) -> SessionEntry | None:
        """Return the session entry for ``session_id`` or ``None``."""
        return self._sessions.get(session_id)

    def list_all(self) -> list[SessionEntry]:
        """Return all live sessions ordered by creation time (oldest first)."""
        return sorted(self._sessions.values(), key=lambda entry: entry.created_at)
