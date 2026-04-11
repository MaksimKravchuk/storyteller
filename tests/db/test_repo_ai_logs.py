"""Tests for ``db.repo_ai_logs.AILogStore`` against a real Postgres."""

from __future__ import annotations

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
class TestMaxCallSequence:
    @allure.story("Max call sequence")
    @allure.title("max_call_sequence returns the highest sequence for a numbered turn")
    @pytest.mark.asyncio
    async def test_max_for_numbered_turn(self, repo: GameRepository, test_session_id: str) -> None:
        logs = [_entry(test_session_id, agent="a", seq=seq) for seq in (1, 5, 3)]
        await repo.ai_logs.save(logs, turn_number=4)

        max_seq = await repo.ai_logs.max_call_sequence(test_session_id, turn_number=4)
        assert max_seq == 5

    @allure.story("Max call sequence")
    @allure.title("max_call_sequence returns None when no logs exist for the session")
    @pytest.mark.asyncio
    async def test_max_returns_none_when_empty(self, repo: GameRepository, test_session_id: str) -> None:
        result = await repo.ai_logs.max_call_sequence(test_session_id, turn_number=None)
        assert result is None

    @allure.story("Max call sequence")
    @allure.title("max_call_sequence handles turn_number IS NULL rows via the unnumbered branch")
    @pytest.mark.asyncio
    async def test_max_for_null_turn(self, repo: GameRepository, test_session_id: str) -> None:
        await repo.ai_logs.save([_entry(test_session_id, agent="a", seq=7)], turn_number=None)
        await repo.ai_logs.save([_entry(test_session_id, agent="b", seq=99)], turn_number=1)

        null_max = await repo.ai_logs.max_call_sequence(test_session_id, turn_number=None)
        assert null_max == 7
