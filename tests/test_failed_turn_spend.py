"""Paid LLM calls from failed turns and parallel NPC turns still reach ``ai_call_logs``.

``ai_call_logs`` is the only input to the global budget gate, so any spend
that never lands there is invisible to the kill switch.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import allure
import pytest

from cast.base_performer_class import _record_llm_call
from config import Config
from interfaces.web import service
from interfaces.web.runtime import ActionPersistence
from llm import call_logger
from llm.message import LLMResponse

_PLAYER_ID = "11111111-1111-1111-1111-111111111111"
_SESSION_ID = "session-1"

pytestmark = [
    allure.epic("Engine & LLM Infrastructure"),
    allure.feature("Cost accounting"),
]


@pytest.fixture(autouse=True)
def _session_buffers():
    call_logger.current_session_id.set(_SESSION_ID)
    call_logger.reset_buffer()
    yield
    call_logger.reset_buffer()
    call_logger.current_session_id.set(None)


def _record_call(agent_name: str) -> None:
    _record_llm_call(agent_name, "gpt-test", LLMResponse(body="ok", usage={}), "system", [])


async def _npc_turn(agent_name: str) -> None:
    _record_call(agent_name)


async def _director_then_fail(*_args: object, **_kwargs: object) -> str:
    _record_call("Director")
    raise RuntimeError("narrator failed")


async def _data_miner_then_fail(*_args: object, **_kwargs: object) -> None:
    _record_call("DataMiner")
    raise RuntimeError("scene builder failed")


def _failing_engine() -> MagicMock:
    engine = MagicMock()
    engine.process_action = _director_then_fail
    engine.start_game = _data_miner_then_fail
    engine.assert_running = MagicMock(return_value=(SimpleNamespace(turn_count=4), MagicMock(), MagicMock()))
    return engine


def _repo() -> MagicMock:
    return MagicMock(
        rollback=AsyncMock(),
        commit=AsyncMock(),
        ai_logs=SimpleNamespace(save=AsyncMock(), usage_by_model=AsyncMock(return_value=[])),
        sessions=SimpleNamespace(
            count_active_web=AsyncMock(return_value=0),
            create_web=AsyncMock(return_value={"id": _SESSION_ID}),
            archive=AsyncMock(),
        ),
    )


def _assert_spend_saved(repo: MagicMock, agent_name: str, turn_number: int | None) -> None:
    save = repo.ai_logs.save
    save.assert_awaited_once()
    assert [entry["agent_name"] for entry in save.await_args.args[0]] == [agent_name]
    assert save.await_args.kwargs == {"turn_number": turn_number, "user_id": _PLAYER_ID}


@allure.story("Parallel NPC turns")
@allure.title("LLM calls made inside asyncio.gather land in the turn's shared call-log buffer")
@pytest.mark.asyncio
async def test_gathered_calls_reach_turn_buffer() -> None:
    await asyncio.gather(_npc_turn("NPC-A"), _npc_turn("NPC-B"))

    agents = [entry["agent_name"] for entry in call_logger.get_and_clear_buffer()]
    assert sorted(agents) == ["NPC-A", "NPC-B"]


@allure.story("Failed turn")
@allure.title("A turn that fails after paid LLM calls rolls back state but commits the call logs")
@pytest.mark.asyncio
async def test_failed_turn_commits_spend() -> None:
    repo = _repo()
    persistence = ActionPersistence(
        repo=repo,
        session_id=_SESSION_ID,
        engine=_failing_engine(),
        action="look",
        language="English",
        user_id=_PLAYER_ID,
    )

    with pytest.raises(RuntimeError, match="narrator failed"):
        await persistence.run()

    repo.rollback.assert_awaited_once()
    # No turn number: the spend counts toward the budget but not toward successful-turn quotas.
    _assert_spend_saved(repo, "Director", turn_number=None)
    repo.commit.assert_awaited_once()


@allure.story("Failed game start")
@allure.title("A game start that fails after paid LLM calls archives the session and commits the call logs")
@pytest.mark.asyncio
async def test_failed_start_commits_spend() -> None:
    repo = _repo()
    start_request = service.StartGameParams(player_id=_PLAYER_ID, setting="Rome", language="English")

    with patch.object(service, "begin_session", new=AsyncMock(return_value=_failing_engine())):
        with pytest.raises(service.GameStartFailedError):
            await service.start_game_for_player(repo, Config(), start_request)

    repo.rollback.assert_awaited_once()
    repo.sessions.archive.assert_awaited_once_with(_SESSION_ID)
    _assert_spend_saved(repo, "DataMiner", turn_number=None)


@allure.story("Failed game start")
@allure.title("A start that fails while building the engine commits no placeholder session")
@pytest.mark.asyncio
async def test_engine_build_failure_commits_no_session() -> None:
    repo = _repo()
    start_request = service.StartGameParams(player_id=_PLAYER_ID, setting="Rome", language="English")

    with patch.object(service, "begin_session", new=AsyncMock(side_effect=RuntimeError("no search key"))):
        with pytest.raises(RuntimeError, match="no search key"):
            await service.start_game_for_player(repo, Config(), start_request)

    repo.commit.assert_not_awaited()
