"""Tests for ``db.repo_ai_logs.AILogStore`` against a real Postgres."""

from __future__ import annotations

from datetime import datetime, timezone

import allure
import pytest

from tests.db.conftest import GameRepository

pytestmark = pytest.mark.db


def _entry(session_id: str, *, agent: str = "director", seq: int | None = None) -> dict:
    return {
        "session_id": session_id,
        "agent_name": agent,
        "model": "test-model",
        "system_prompt": "You are helpful.",
        "messages": [{"role": "user", "content": "hi"}],
        "response_content": "ok",
        "prompt_tokens": 10,
        "completion_tokens": 5,
        "duration_ms": 25,
        "call_sequence": seq,
        "parent_agent": None,
    }


@allure.epic("Memory & Persistence")
@allure.feature("AI call logs")
class TestSave:
    @allure.story("Save")
    @allure.title("save with an empty list is a no-op and writes nothing")
    @pytest.mark.asyncio
    async def test_empty_list_is_noop(self, repo: GameRepository, test_session_id: str) -> None:
        await repo.ai_logs.save([])
        rows = await repo.ai_logs.get(test_session_id)
        assert rows == []

    @allure.story("Save")
    @allure.title("save batch-inserts logs with turn_number and JSONB messages payload")
    @pytest.mark.asyncio
    async def test_batch_insert_with_turn(self, repo: GameRepository, test_session_id: str) -> None:
        logs = [_entry(test_session_id, agent="director", seq=1), _entry(test_session_id, agent="actor", seq=2)]
        await repo.ai_logs.save(logs, turn_number=1)

        rows = await repo.ai_logs.get(test_session_id, turn_number=1)
        assert len(rows) == 2
        agents = {row["agent_name"] for row in rows}
        assert agents == {"director", "actor"}
        assert all(row["turn_number"] == 1 for row in rows)
        first_row = rows[0]
        assert first_row["messages"] == [{"role": "user", "content": "hi"}]


@allure.epic("Memory & Persistence")
@allure.feature("AI call logs")
class TestGet:
    @allure.story("Get")
    @allure.title("get(turn_number=N) filters out logs from other turns")
    @pytest.mark.asyncio
    async def test_filters_by_turn(self, repo: GameRepository, test_session_id: str) -> None:
        await repo.ai_logs.save([_entry(test_session_id, agent="a", seq=1)], turn_number=1)
        await repo.ai_logs.save([_entry(test_session_id, agent="b", seq=1)], turn_number=2)

        turn_one = await repo.ai_logs.get(test_session_id, turn_number=1)
        assert len(turn_one) == 1
        assert turn_one[0]["agent_name"] == "a"

    @allure.story("Get")
    @allure.title("get(limit=N) truncates results while preserving created_at order")
    @pytest.mark.asyncio
    async def test_limit_truncates(self, repo: GameRepository, test_session_id: str) -> None:
        batch = [_entry(test_session_id, agent="agent-{0}".format(idx), seq=idx) for idx in range(5)]
        await repo.ai_logs.save(batch, turn_number=3)

        limited = await repo.ai_logs.get(test_session_id, turn_number=3, limit=2)
        assert len(limited) == 2


@allure.epic("Memory & Persistence")
@allure.feature("AI call logs")
class TestTurnCount:
    @allure.story("Beta quotas")
    @allure.title("turn_count_for_user counts same turn number in separate sessions")
    @pytest.mark.asyncio
    async def test_counts_turns_across_sessions(self, repo: GameRepository, test_session_id: str) -> None:
        player_id = "11111111-1111-1111-1111-111111111111"
        second_session = await repo.sessions.create_web(player_id)
        await repo.ai_logs.save([_entry(test_session_id)], turn_number=1, user_id=player_id)
        await repo.ai_logs.save([_entry(second_session["id"])], turn_number=1, user_id=player_id)

        count = await repo.ai_logs.turn_count_for_user(
            player_id,
            start_at=datetime(2000, 1, 1, tzinfo=timezone.utc),
            end_at=datetime(2100, 1, 1, tzinfo=timezone.utc),
        )

        assert count == 2
