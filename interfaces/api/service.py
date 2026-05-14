"""Service-layer helpers for the mobile API.

Keeps the route module thin: route handlers stay parse-input → call-service
→ translate-exceptions, and any logic that touches the engine/session
store lives here.
"""

from __future__ import annotations

from interfaces.api.engine_factory import EngineFactory
from interfaces.api.schemas import CreateSessionRequest, SessionState, SessionSummary
from interfaces.api.service_helpers import entry_to_state, entry_to_summary
from interfaces.api.sessions import SessionEntry, SessionStore


class SessionNotFoundError(Exception):
    """Raised when a session_id does not resolve in the store."""


async def create_session(
    *,
    body: CreateSessionRequest,
    store: SessionStore,
    engine_factory: EngineFactory,
) -> SessionEntry:
    """Build an engine, start the game, and register it as a new session."""
    engine = engine_factory.build(body.language)
    opening = await engine.start_game(body.setting)
    return store.create(
        engine=engine,
        setting=body.setting,
        language=body.language,
        opening_scene=opening,
    )


async def process_action(
    *,
    session_id: str,
    action: str,
    store: SessionStore,
) -> tuple[SessionEntry, str]:
    """Run a player action through the session's engine and update the transcript.

    Acquires the session's lock to serialise concurrent action requests.
    Returns ``(entry, narration)`` on success; raises ``SessionNotFoundError``
    if the session_id is unknown.
    """
    entry = store.get(session_id)
    if entry is None:
        raise SessionNotFoundError(session_id)
    async with entry.lock:
        narration = await entry.engine.process_action(action)
        entry.add_turn("player", action)
        entry.add_turn("narrator", narration)
    return entry, narration


def get_session_state(session_id: str, store: SessionStore) -> SessionState:
    """Build the full ``SessionState`` payload for one session."""
    entry = store.get(session_id)
    if entry is None:
        raise SessionNotFoundError(session_id)
    return entry_to_state(entry)


def list_sessions(store: SessionStore) -> list[SessionSummary]:
    """Return a compact summary of every live session."""
    return [entry_to_summary(entry) for entry in store.list_all()]
