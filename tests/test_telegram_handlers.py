"""Tests for interfaces.telegram_handlers — awaiting_setting, playing, persist."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import allure
import pytest

from tests._telegram_helpers import make_text_update

pytest.importorskip("telegram")

from interfaces import telegram_handlers as handlers  # noqa: E402

pytestmark = [
    allure.epic("Player Interfaces"),
    allure.feature("Telegram handlers"),
]


def _make_ctx(text: str = "hello", state_language: str = "English") -> SimpleNamespace:
    """Build a MessageContext-like namespace understood by handler functions."""
    update = make_text_update(text=text)
    repo = AsyncMock()
    repo.save_game_state = AsyncMock()
    repo.update_session = AsyncMock()
    repo.rollback = AsyncMock()
    repo.load_game_state = AsyncMock()
    repo.ai_logs = MagicMock()
    repo.ai_logs.save = AsyncMock()
    return SimpleNamespace(
        update=update,
        repo=repo,
        session_id="sess-1",
        text=text,
        cfg=SimpleNamespace(telegram_bot_token="TKN"),
        language=state_language,
    )


def _make_engine(with_state: bool = True) -> MagicMock:
    engine = MagicMock()
    engine.start_game = AsyncMock(return_value="Once upon a time in Rome...")
    engine.process_action = AsyncMock(return_value="You walk through the forum.")
    if with_state:
        engine.game_state = SimpleNamespace(turn_count=3)
        engine.knowledge_graph = MagicMock()
        engine.event_manager = SimpleNamespace(all_events=[])
    else:
        engine.game_state = None
        engine.knowledge_graph = None
        engine.event_manager = None
    return engine


def _last_reply(ctx: SimpleNamespace) -> str:
    reply_mock = ctx.update.message.reply_text
    return reply_mock.call_args_list[-1].args[0]


@allure.story("persist_engine_state")
@allure.title("persist_engine_state saves game state and flushes buffered AI call logs")
@pytest.mark.asyncio
async def test_persist_engine_state_flushes_ai_logs() -> None:
    ctx = _make_ctx()
    engine = _make_engine(with_state=True)
    logs = [{"call_id": "c1"}]

    with patch("interfaces.telegram_handlers.get_and_clear_buffer", return_value=logs):
        await handlers.persist_engine_state(ctx.repo, ctx.session_id, engine, turn_number=3)

    ctx.repo.save_game_state.assert_awaited_once()
    ctx.repo.ai_logs.save.assert_awaited_once_with(logs, turn_number=3)


@allure.story("persist_engine_state")
@allure.title("persist_engine_state skips ai_logs.save when the buffer is empty")
@pytest.mark.asyncio
async def test_persist_engine_state_skips_empty_ai_logs() -> None:
    ctx = _make_ctx()
    engine = _make_engine(with_state=True)

    with patch("interfaces.telegram_handlers.get_and_clear_buffer", return_value=[]):
        await handlers.persist_engine_state(ctx.repo, ctx.session_id, engine, turn_number=None)

    ctx.repo.save_game_state.assert_awaited_once()
    ctx.repo.ai_logs.save.assert_not_awaited()


@allure.story("persist_engine_state")
@allure.title("persist_engine_state raises RuntimeError when engine.game_state is None")
@pytest.mark.asyncio
async def test_persist_engine_state_raises_when_no_game_state() -> None:
    ctx = _make_ctx()
    engine = _make_engine(with_state=False)

    with pytest.raises(RuntimeError, match="game_state is None"):
        await handlers.persist_engine_state(ctx.repo, ctx.session_id, engine, turn_number=None)


@allure.story("handle_awaiting_setting")
@allure.title("handle_awaiting_setting starts a new game and replies with opening narration")
@pytest.mark.asyncio
async def test_handle_awaiting_setting_happy_path() -> None:
    ctx = _make_ctx(text="Medieval France")
    engine = _make_engine(with_state=True)

    with (
        patch("interfaces.telegram_handlers.create_engine", return_value=engine),
        patch(
            "interfaces.telegram_handlers.get_and_clear_buffer",
            return_value=[],
        ),
    ):
        await handlers.handle_awaiting_setting(ctx, chat_id=42)

    engine.start_game.assert_awaited_once_with("Medieval France")
    ctx.repo.save_game_state.assert_awaited_once()
    ctx.repo.update_session.assert_awaited_once_with("sess-1", state="playing")
    ctx.repo.rollback.assert_not_awaited()
    # Two replies: the "researching..." notice and the opening narration.
    replies_expected = 2
    assert ctx.update.message.reply_text.await_count == replies_expected


@allure.story("handle_awaiting_setting")
@allure.title("handle_awaiting_setting rolls back and resets to idle when the engine raises")
@pytest.mark.asyncio
async def test_handle_awaiting_setting_engine_exception_rolls_back() -> None:
    ctx = _make_ctx(text="Boom")
    engine = _make_engine(with_state=True)
    engine.start_game = AsyncMock(side_effect=RuntimeError("boom"))

    with patch("interfaces.telegram_handlers.create_engine", return_value=engine):
        await handlers.handle_awaiting_setting(ctx, chat_id=42)

    ctx.repo.rollback.assert_awaited_once()
    ctx.repo.update_session.assert_awaited_once_with("sess-1", state="idle")
    # Two replies: "Researching..." then the error message.
    replies_expected = 2
    assert ctx.update.message.reply_text.await_count == replies_expected
    assert "wrong" in _last_reply(ctx).lower()


@allure.story("handle_playing")
@allure.title("handle_playing resets session to idle when no saved game state is found")
@pytest.mark.asyncio
async def test_handle_playing_missing_state_resets() -> None:
    ctx = _make_ctx(text="look around")
    ctx.repo.load_game_state = AsyncMock(return_value=None)

    await handlers.handle_playing(ctx)

    ctx.repo.update_session.assert_awaited_once_with("sess-1", state="idle")
    ctx.update.message.reply_text.assert_awaited_once()
    assert "No game" in _last_reply(ctx)


@allure.story("handle_playing")
@allure.title("handle_playing rehydrates engine, processes action and persists state")
@pytest.mark.asyncio
async def test_handle_playing_happy_path() -> None:
    ctx = _make_ctx(text="attack goblin")
    engine = _make_engine(with_state=True)
    loaded_state = SimpleNamespace(turn_count=2)
    loaded_graph = MagicMock()
    loaded_events: list = []
    ctx.repo.load_game_state = AsyncMock(return_value=(loaded_state, loaded_graph, loaded_events))

    create_mock = AsyncMock(return_value=engine)
    with (
        patch(
            "interfaces.telegram_handlers.create_engine_from_state",
            new=create_mock,
        ),
        patch(
            "interfaces.telegram_handlers.get_and_clear_buffer",
            return_value=[{"call_id": "c1"}],
        ),
    ):
        await handlers.handle_playing(ctx)

    create_mock.assert_awaited_once()
    engine.process_action.assert_awaited_once_with("attack goblin")
    ctx.repo.save_game_state.assert_awaited_once()
    ctx.repo.ai_logs.save.assert_awaited_once()
    ctx.update.message.reply_text.assert_awaited_once()


@allure.story("handle_playing")
@allure.title("handle_playing replies with an error when process_action raises but does not reset state")
@pytest.mark.asyncio
async def test_handle_playing_process_action_exception() -> None:
    ctx = _make_ctx(text="explode")
    engine = _make_engine(with_state=True)
    engine.process_action = AsyncMock(side_effect=RuntimeError("kaboom"))
    loaded: tuple = (SimpleNamespace(turn_count=1), MagicMock(), [])
    ctx.repo.load_game_state = AsyncMock(return_value=loaded)

    with patch(
        "interfaces.telegram_handlers.create_engine_from_state",
        new=AsyncMock(return_value=engine),
    ):
        await handlers.handle_playing(ctx)

    ctx.repo.update_session.assert_not_awaited()
    ctx.repo.save_game_state.assert_not_awaited()
    ctx.update.message.reply_text.assert_awaited_once()
    assert "wrong" in _last_reply(ctx).lower()
