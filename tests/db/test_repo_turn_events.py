"""Tests for ``db.repo_turn_events.TurnEventStore`` against a real Postgres."""

from __future__ import annotations

import allure
import pytest

from tests.db.conftest import GameRepository

pytestmark = pytest.mark.db


def _event(*, event_type: str, sequence: int, npc_id: str | None = None) -> dict:
    return {
        "event_type": event_type,
        "agent_name": "Director",
        "npc_id": npc_id,
        "payload": {"outcome": "actor_succeeds"},
        "sequence": sequence,
    }


@allure.epic("Memory & Persistence")
@allure.feature("Turn events")
class TestSave:
    @allure.story("Save")
    @allure.title("save with an empty list is a no-op and writes nothing")
    @pytest.mark.asyncio
    async def test_empty_list_noop(self, repo: GameRepository, test_session_id: str) -> None:
        await repo.turn_events.save([], session_id=test_session_id, turn_number=1)

        rows = await repo.turn_events.get(test_session_id)
        assert rows == []

    @allure.story("Save")
    @allure.title("save batch-inserts events with turn_number + scene_number context")
    @pytest.mark.asyncio
    async def test_batch_insert(self, repo: GameRepository, test_session_id: str) -> None:
        events = [_event(event_type="dice_contest", sequence=0), _event(event_type="item_list", sequence=1)]

        await repo.turn_events.save(
            events,
            session_id=test_session_id,
            turn_number=3,
            scene_number=2,
        )

        rows = await repo.turn_events.get(test_session_id)
        assert len(rows) == 2
        assert all(row["turn_number"] == 3 for row in rows)
        assert all(row["scene_number"] == 2 for row in rows)


@allure.epic("Memory & Persistence")
@allure.feature("Turn events")
class TestGet:
    @allure.story("Get")
    @allure.title("get(turn_number=N) filters out events from other turns")
    @pytest.mark.asyncio
    async def test_filter_by_turn(self, repo: GameRepository, test_session_id: str) -> None:
        await repo.turn_events.save(
            [_event(event_type="dice_contest", sequence=0)],
            session_id=test_session_id,
            turn_number=1,
        )
        await repo.turn_events.save(
            [_event(event_type="dice_contest", sequence=0)],
            session_id=test_session_id,
            turn_number=2,
        )

        turn_one = await repo.turn_events.get(test_session_id, turn_number=1)
        assert len(turn_one) == 1
        assert turn_one[0]["turn_number"] == 1

    @allure.story("Get")
    @allure.title("get(npc_id=X) filters events to those linked to that NPC")
    @pytest.mark.asyncio
    async def test_filter_by_npc(self, repo: GameRepository, test_session_id: str) -> None:
        npc_uuid = "11111111-1111-1111-1111-111111111111"
        other_uuid = "22222222-2222-2222-2222-222222222222"
        await repo.turn_events.save(
            [
                _event(event_type="dice_contest", sequence=0, npc_id=npc_uuid),
                _event(event_type="dice_contest", sequence=1, npc_id=other_uuid),
            ],
            session_id=test_session_id,
            turn_number=4,
        )

        matching = await repo.turn_events.get(test_session_id, npc_id=npc_uuid)
        assert len(matching) == 1
        assert str(matching[0]["npc_id"]) == npc_uuid

    @allure.story("Get")
    @allure.title("get(event_type=T) filters events by type")
    @pytest.mark.asyncio
    async def test_filter_by_type(self, repo: GameRepository, test_session_id: str) -> None:
        await repo.turn_events.save(
            [
                _event(event_type="dice_contest", sequence=0),
                _event(event_type="item_list", sequence=1),
            ],
            session_id=test_session_id,
            turn_number=5,
        )

        items = await repo.turn_events.get(test_session_id, event_type="item_list")
        assert len(items) == 1
        assert items[0]["event_type"] == "item_list"
