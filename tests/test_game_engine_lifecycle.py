"""Tests for GameEngine.start_game / process_action / restore_session lifecycle."""

from __future__ import annotations

from contextlib import ExitStack
from unittest.mock import AsyncMock, MagicMock, patch

import allure
import pytest

from engine.game_engine import GameEngine
from knowledge.graph import KnowledgeGraph
from models.game_state import GameState

pytestmark = [
    allure.epic("Engine & LLM Infrastructure"),
    allure.feature("GameEngine lifecycle"),
]

_OPENING_NARRATION = "You stand in a sunlit forum."
_PLAYER_ACTION_REPLY = "You move forward."


class _StubClients:
    """Namespace mimicking the LLMClients NamedTuple with MagicMock clients."""

    def __init__(self) -> None:
        self.director = MagicMock(name="director_client")
        self.agent = MagicMock(name="agent_client")
        self.narrator = MagicMock(name="narrator_client")


def _make_director_mock(reply: str) -> MagicMock:
    director = MagicMock()
    director.execute = AsyncMock(return_value=reply)
    return director


class _StartGameHarness:
    """Bundle every patch and stub required to exercise ``GameEngine.start_game``."""

    def __init__(self, setting, reply: str = _OPENING_NARRATION) -> None:
        self.clients = _StubClients()
        self.director = _make_director_mock(reply)
        self.data_miner = MagicMock(name="data_miner_instance")
        self.data_miner.execute = AsyncMock(return_value=setting)
        self._stack = ExitStack()
        self.wire_mock: MagicMock | None = None
        self.populate_mock: MagicMock | None = None

    def __enter__(self) -> "_StartGameHarness":
        self._stack.__enter__()
        self._stack.enter_context(
            patch("engine.game_engine.create_llm_clients", return_value=self.clients),
        )
        self.data_miner_cls: MagicMock = self._stack.enter_context(
            patch("engine.game_engine.DataMiner", return_value=self.data_miner),
        )
        self.wire_mock = self._stack.enter_context(
            patch("engine.game_engine.wire_director", return_value=self.director),
        )
        self.populate_mock = self._stack.enter_context(
            patch("engine.game_engine.populate_graph_from_setting"),
        )
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self._stack.__exit__(exc_type, exc, tb)


@allure.story("start_game wiring")
@allure.title("start_game populates internal state, graph, and event manager from the DataMiner setting")
@pytest.mark.asyncio
async def test_start_game_populates_internal_state(simple_setting) -> None:
    """start_game must call wire_director and initialise the internal state triple."""
    engine = GameEngine()
    with _StartGameHarness(simple_setting) as harness:
        opening = await engine.start_game("Ancient Rome during Augustus")
        harness.data_miner.execute.assert_awaited_once_with("Ancient Rome during Augustus")
        harness.director.execute.assert_awaited_once()

    assert opening == _OPENING_NARRATION
    game_state, knowledge_graph, event_manager = engine.assert_running()
    assert isinstance(knowledge_graph, KnowledgeGraph)
    assert event_manager is not None
    assert game_state.setting is simple_setting


@allure.story("start_game wiring")
@allure.title("start_game passes the DataMiner instance into wire_director so agents share research state")
@pytest.mark.asyncio
async def test_start_game_wires_director_with_data_miner(simple_setting) -> None:
    """wire_director must receive the DataMiner instance as its 4th positional argument."""
    engine = GameEngine(language="Italian")
    with _StartGameHarness(simple_setting) as harness:
        await engine.start_game("Medieval Florence")
        assert harness.wire_mock is not None
        harness.wire_mock.assert_called_once()
        call = harness.wire_mock.call_args
        assert call.args[0] is harness.clients
        assert call.args[4] == "Italian"
        assert call.args[5] is harness.data_miner


@allure.story("start_game wiring")
@allure.title("start_game builds the initial DataMiner with the engine's session language")
@pytest.mark.asyncio
async def test_start_game_builds_data_miner_with_session_language(simple_setting) -> None:
    """DataMiner constructed during setting research must localise to the engine's session language.

    Regression guard: earlier versions built the initial DataMiner with the default ``language="English"``,
    so a Russian session received English setting data and every downstream agent's system prompt ended up
    layered over an English summary. Cross-check against ``wire_director``'s ``data_miner or DataMiner(...)``
    short-circuit — the pre-built instance wins, so it must be localised here at construction time.
    """
    engine = GameEngine(language="Russian")
    with _StartGameHarness(simple_setting) as harness:
        await engine.start_game("Санкт-Петербург при Петре I")
        harness.data_miner_cls.assert_called_once()
        assert harness.data_miner_cls.call_args.kwargs["language"] == "Russian"


@allure.story("process_action guard")
@allure.title("process_action raises RuntimeError when called before start_game")
@pytest.mark.asyncio
async def test_process_action_before_start_raises() -> None:
    """process_action must refuse to run before start_game has wired a Director."""
    engine = GameEngine()
    with pytest.raises(RuntimeError, match="Game not started"):
        await engine.process_action("look")


@allure.story("process_action delegation")
@allure.title("process_action delegates the raw player input to director.execute and returns its narration")
@pytest.mark.asyncio
async def test_process_action_delegates_to_director(simple_setting) -> None:
    """Once started, process_action forwards the player action to the Director."""
    engine = GameEngine()
    with _StartGameHarness(simple_setting) as harness:
        await engine.start_game("Any setting")
        harness.director.execute = AsyncMock(return_value=_PLAYER_ACTION_REPLY)
        reply = await engine.process_action("go north")
        harness.director.execute.assert_awaited_once_with("go north")

    assert reply == _PLAYER_ACTION_REPLY


@allure.story("assert_running")
@allure.title("assert_running raises before start and returns live objects after start")
@pytest.mark.asyncio
async def test_assert_running_covers_both_states(simple_setting) -> None:
    """assert_running raises when the engine is not started and returns the state triple after start."""
    engine = GameEngine()
    with pytest.raises(RuntimeError, match="Game not started"):
        engine.assert_running()

    with _StartGameHarness(simple_setting):
        await engine.start_game("setting")

    _, knowledge_graph, event_manager = engine.assert_running()
    assert isinstance(knowledge_graph, KnowledgeGraph)
    assert event_manager is not None


@allure.story("restore_session")
@allure.title("restore_session rebuilds event manager, wires director, and restores actors from saved state")
@pytest.mark.asyncio
async def test_restore_session_wires_director_and_restores_actors(simple_setting) -> None:
    """restore_session must delegate to wire_director and restore_actors with injected state."""
    clients = _StubClients()
    director = _make_director_mock("restored")
    graph = KnowledgeGraph()
    saved_state = GameState(setting=simple_setting, knowledge_graph=graph)

    engine = GameEngine(language="French")
    with (
        patch("engine.game_engine.create_llm_clients", return_value=clients),
        patch("engine.game_engine.wire_director", return_value=director) as wire_mock,
        patch("engine.game_engine.restore_actors") as restore_mock,
    ):
        await engine.restore_session(saved_state, graph, [])
        wire_mock.assert_called_once()
        wire_call = wire_mock.call_args
        assert wire_call.args[0] is clients
        assert wire_call.args[4] == "French"
        restore_mock.assert_called_once()
        restore_args = restore_mock.call_args.args
        assert restore_args[0] is director
        assert restore_args[1] is saved_state
        assert restore_args[2] is graph
        assert restore_args[3] is clients.agent
        assert restore_args[4] == "French"

    game_state, knowledge_graph, event_manager = engine.assert_running()
    assert game_state is saved_state
    assert knowledge_graph is graph
    assert event_manager is not None
    assert event_manager.all_events == []
