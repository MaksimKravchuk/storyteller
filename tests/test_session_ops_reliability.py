"""Consumer-seam test: reliability snapshot reaches turn_events at turn boundary."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import allure
import pytest

from cast import _reliability_metrics as reliability_metrics
from engine import session_ops, session_restore
from llm import call_logger, turn_event_logger

pytestmark = [
    allure.epic("Engine & LLM Infrastructure"),
    allure.feature("Reliability metering"),
]


def _make_repo() -> MagicMock:
    repo = MagicMock()
    repo.save_game_state = AsyncMock()
    repo.ai_logs = MagicMock()
    repo.ai_logs.save = AsyncMock()
    repo.turn_events = MagicMock()
    repo.turn_events.save = AsyncMock()
    return repo


def _make_engine() -> MagicMock:
    engine = MagicMock()
    game_state = SimpleNamespace(turn_count=1, scene_number=2, uuid=None)
    engine.assert_running = MagicMock(
        return_value=(game_state, MagicMock(), SimpleNamespace(all_events=[])),
    )
    return engine


@allure.story("Turn boundary snapshot")
@allure.title("persist_engine_state records a reliability_snapshot turn event when counters are non-empty")
@pytest.mark.asyncio
async def test_snapshot_event_lands_in_turn_events() -> None:
    call_logger.current_session_id.set("sess-1")
    turn_event_logger.reset_events()
    reliability_metrics.reset_counters()
    reliability_metrics.record_fallback("dramaturge", "consistency_pass")
    reliability_metrics.record_retry("Director", attempt=1)
    repo = _make_repo()

    await session_ops.persist_engine_state(repo, "sess-1", _make_engine(), turn_number=4)

    repo.turn_events.save.assert_awaited_once()
    saved_events, save_kwargs = repo.turn_events.save.call_args.args, repo.turn_events.save.call_args.kwargs
    flushed = saved_events[0]
    assert save_kwargs == {"session_id": "sess-1", "turn_number": 4, "scene_number": 2}
    reliability_events = [event for event in flushed if event["event_type"] == "reliability_snapshot"]
    assert len(reliability_events) == 1
    payload = reliability_events[0]["payload"]
    assert {"agent": "Director", "event_type": "validation_retry", "count": 1} in payload["counters"]
    assert {"agent": "dramaturge", "event_type": "silent_fallback", "count": 1} in payload["counters"]


@allure.story("Turn boundary snapshot")
@allure.title("persist_engine_state skips the reliability_snapshot event when counters are empty")
@pytest.mark.asyncio
async def test_snapshot_event_skipped_when_no_counters() -> None:
    call_logger.current_session_id.set("sess-2")
    turn_event_logger.reset_events()
    reliability_metrics.reset_counters()
    repo = _make_repo()

    await session_ops.persist_engine_state(repo, "sess-2", _make_engine(), turn_number=5)

    # No reliability_snapshot recorded means no turn_events were buffered either.
    repo.turn_events.save.assert_not_awaited()


@allure.story("Turn boundary snapshot")
@allure.title("_bind_session_buffers resets the reliability counter map for the new turn")
def test_bind_session_buffers_resets_counters() -> None:
    reliability_metrics.reset_counters()
    reliability_metrics.record_fallback("narrator", "visible_entities")

    session_ops._bind_session_buffers("sess-rebind")

    assert reliability_metrics.snapshot_counters() == {}


@allure.story("Admin overrides on resume")
@allure.title("resume_session passes admin model and search overrides")
@pytest.mark.asyncio
async def test_resume_session_applies_admin_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    """Consumer seam: resume passes the admin overrides into engine construction."""
    repo = MagicMock()
    repo.load_game_state = AsyncMock(return_value=(MagicMock(), MagicMock(), []))
    role_overrides, search = {"narrator": MagicMock()}, MagicMock()
    monkeypatch.setattr(session_restore, "load_role_overrides", AsyncMock(return_value=role_overrides))
    monkeypatch.setattr(session_restore, "load_search_override", AsyncMock(return_value=search))
    engine = MagicMock()
    engine.restore_session = AsyncMock()
    create = MagicMock(return_value=engine)
    monkeypatch.setattr(session_restore, "create_engine", create)

    await session_ops.resume_session(repo, MagicMock(), "sid")

    assert create.call_args.args[2] is role_overrides
    assert create.call_args.kwargs["search_override"] is search
    engine.restore_session.assert_awaited_once()
