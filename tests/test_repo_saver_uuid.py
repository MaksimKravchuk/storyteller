"""Unit-level regression test for ``db.repo_saver.StateSaver``.

Specifically guards against the ``snapshot_from_engine`` / ``restore_engine``
mismatch that surfaced when a player started a second game on the same web
session: the upsert on ``session_id`` keeps the existing row's ``id``, so the
newly-generated ``game_state.uuid`` used to end up returned in the snapshot
while the DB carried the old id, causing the next ``/api/games/{id}/actions``
call to fail the ownership check with "Game not found".

This test uses a mocked ``AsyncSession`` and therefore runs anywhere — no
Postgres / testcontainers needed.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import allure
import pytest

from db.repo_saver import StateSaver
from knowledge.graph import KnowledgeGraph
from models.game_state import GameState
from models.setting import Setting


pytestmark = [
    allure.epic("Memory & Persistence"),
    allure.feature("State saver"),
]


def _fresh_game_state() -> GameState:
    setting = Setting(
        name="Rome",
        time_period="1 AD",
        region="Italy",
        summary="Eternal city",
    )
    return GameState(setting=setting, knowledge_graph=KnowledgeGraph())


def _mock_session_returning(existing_id: str) -> AsyncMock:
    """Build an AsyncSession mock whose first ``execute`` returns ``existing_id``."""
    session = AsyncMock()
    upsert_result = MagicMock()
    upsert_result.scalar_one.return_value = existing_id
    session.execute.return_value = upsert_result
    return session


@allure.story("Replace game")
@allure.title(
    "save() aligns game_state.uuid with the id the DB kept on ON CONFLICT (session_id)",
)
@pytest.mark.asyncio
async def test_save_aligns_uuid_with_db_returned_id() -> None:
    existing_id = "00000000-0000-0000-0000-000000000001"
    session = _mock_session_returning(existing_id)

    game_state = _fresh_game_state()
    assert game_state.uuid != existing_id  # new engine uuid, never seen by DB

    saver = StateSaver(session)
    await saver.save("session-xyz", game_state, game_state.knowledge_graph, [])

    assert game_state.uuid == existing_id
