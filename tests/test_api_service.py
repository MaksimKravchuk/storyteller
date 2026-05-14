"""Tests for the API service layer in ``interfaces.api.service``."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import allure
import pytest

from interfaces.api import service
from interfaces.api.schemas import CreateSessionRequest
from interfaces.api.sessions import SessionStore

pytestmark = [
    allure.epic("Player Interfaces"),
    allure.feature("Mobile API"),
]


def _running_engine_mock(narration: str = "ok", turn_count: int = 1) -> MagicMock:
    """Return a MagicMock engine that satisfies the ``assert_running`` contract."""
    engine = MagicMock()
    engine.start_game = AsyncMock(return_value="opening")
    engine.process_action = AsyncMock(return_value=narration)
    state = MagicMock(
        current_scene=MagicMock(description="scene"),
        player=MagicMock(inventory=[]),
        turn_count=turn_count,
    )
    engine.assert_running = MagicMock(return_value=(state, MagicMock(), MagicMock()))
    return engine


class _Factory:
    def __init__(self, engine: MagicMock) -> None:
        self.engine = engine

    def build(self, language: str):
        return self.engine


@allure.story("Service layer")
@allure.title("create_session drives the engine through start_game and registers a session in the store")
@pytest.mark.asyncio
async def test_create_session_drives_engine_and_registers() -> None:
    store = SessionStore()
    engine = _running_engine_mock()
    entry = await service.create_session(
        body=CreateSessionRequest(setting="Rome", language="English"),
        store=store,
        engine_factory=_Factory(engine),
    )
    engine.start_game.assert_awaited_once_with("Rome")
    assert store.get(entry.session_id) is entry
    assert entry.opening_scene == "opening"


@allure.story("Service layer")
@allure.title("process_action raises SessionNotFoundError when the session_id is unknown")
@pytest.mark.asyncio
async def test_process_action_raises_for_unknown_session() -> None:
    with pytest.raises(service.SessionNotFoundError):
        await service.process_action(
            session_id="missing",
            action="look",
            store=SessionStore(),
        )


@allure.story("Service layer")
@allure.title("process_action drives the engine and appends player+narrator entries to the transcript")
@pytest.mark.asyncio
async def test_process_action_updates_transcript() -> None:
    store = SessionStore()
    engine = _running_engine_mock(narration="You move.", turn_count=2)
    entry = await service.create_session(
        body=CreateSessionRequest(setting="Rome", language="English"),
        store=store,
        engine_factory=_Factory(engine),
    )

    returned, narration = await service.process_action(
        session_id=entry.session_id,
        action="look",
        store=store,
    )
    assert returned is entry
    assert narration == "You move."
    assert entry.transcript[-2:] == [
        {"role": "player", "text": "look"},
        {"role": "narrator", "text": "You move."},
    ]


@allure.story("Service layer")
@allure.title("get_session_state raises SessionNotFoundError when the session_id is unknown")
def test_get_session_state_raises_for_unknown_session() -> None:
    with pytest.raises(service.SessionNotFoundError):
        service.get_session_state("missing", SessionStore())
