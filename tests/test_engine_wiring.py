"""Tests for engine.engine_wiring — create_llm_clients / wire_director / restore_actors."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import allure

from cast.director import Director
from defaults.models import ModelConfig
from engine.engine_wiring import (
    DirectorContext,
    LLMClients,
    create_llm_clients,
    restore_actors,
    wire_director,
)
from models.npc_card import NPCCard
from timeline.event_manager import EventManager

pytestmark = [
    allure.epic("Engine & LLM Infrastructure"),
    allure.feature("Engine wiring"),
]

_OPENAI = "openai"
_ANTHROPIC = "anthropic"
_DIRECTOR_MODEL = ModelConfig(provider=_OPENAI, model_id="gpt-4")
_AGENT_MODEL = ModelConfig(provider=_ANTHROPIC, model_id="claude-sonnet-4-20250514")
_NARRATOR_MODEL = ModelConfig(provider=_OPENAI, model_id="gpt-4")


@allure.story("create_llm_clients")
@allure.title("create_llm_clients returns an LLMClients triple containing one client per role")
def test_create_llm_clients_returns_triple() -> None:
    """create_llm_clients returns a NamedTuple of three distinct clients."""
    fake_clients = [MagicMock(name="director"), MagicMock(name="agent"), MagicMock(name="narrator")]
    api_keys: dict[str, str | None] = {_OPENAI: "ok", _ANTHROPIC: "ak"}
    with patch(
        "engine.engine_wiring.create_llm_client",
        side_effect=fake_clients,
    ):
        clients = create_llm_clients(
            _DIRECTOR_MODEL,
            _AGENT_MODEL,
            _NARRATOR_MODEL,
            api_keys,
        )
    assert isinstance(clients, LLMClients)
    assert clients.director is fake_clients[0]
    assert clients.agent is fake_clients[1]
    assert clients.narrator is fake_clients[2]


@allure.story("create_llm_clients")
@allure.title("create_llm_clients routes the per-provider API key to each role based on its ModelConfig")
def test_create_llm_clients_routes_api_keys_per_provider() -> None:
    """The api_keys dict is dispatched based on each model's provider."""
    api_keys: dict[str, str | None] = {_OPENAI: "openai-key", _ANTHROPIC: "anthropic-key"}
    with patch("engine.engine_wiring.create_llm_client") as factory:
        create_llm_clients(_DIRECTOR_MODEL, _AGENT_MODEL, _NARRATOR_MODEL, api_keys)
        assert factory.call_count == 3
        call_list = factory.call_args_list
        assert call_list[0].args == (_DIRECTOR_MODEL,)
        assert call_list[0].kwargs == {"api_key": "openai-key"}
        assert call_list[1].args == (_AGENT_MODEL,)
        assert call_list[1].kwargs == {"api_key": "anthropic-key"}
        assert call_list[2].args == (_NARRATOR_MODEL,)
        assert call_list[2].kwargs == {"api_key": "openai-key"}


def _fake_llm_clients() -> LLMClients:
    return LLMClients(
        director=MagicMock(name="director_llm"),
        agent=MagicMock(name="agent_llm"),
        narrator=MagicMock(name="narrator_llm"),
    )


@allure.story("wire_director")
@allure.title("wire_director builds a Director bound to the supplied game_state and knowledge graph")
def test_wire_director_builds_director_with_deps(game_state, populated_graph) -> None:
    """wire_director must produce a Director whose deps reference the supplied graph/state."""
    clients = _fake_llm_clients()
    event_manager = EventManager(game_state=game_state, knowledge_graph=populated_graph)
    ctx = DirectorContext(game_state, event_manager, populated_graph)

    director = wire_director(clients, ctx, "English")

    assert isinstance(director, Director)
    assert director._deps.game_state is game_state
    assert director._deps.event_manager is event_manager
    assert director._deps.memory_manager._graph is populated_graph


@allure.story("wire_director")
@allure.title("wire_director uses the injected DataMiner instance instead of creating a fresh one")
def test_wire_director_uses_injected_data_miner(game_state, populated_graph) -> None:
    """When a data_miner is passed in, wire_director must reuse it on the Director cast."""
    clients = _fake_llm_clients()
    event_manager = EventManager(game_state=game_state, knowledge_graph=populated_graph)
    ctx = DirectorContext(game_state, event_manager, populated_graph)
    injected_miner = MagicMock(name="shared_miner")

    director = wire_director(clients, ctx, "English", data_miner=injected_miner)

    assert director._cast.data_miner is injected_miner


class _ActorRecorder:
    """Callable that returns MagicMocks while recording the npc kwarg passed in."""

    def __init__(self) -> None:
        self.created: list[MagicMock] = []

    def __call__(self, **kwargs) -> MagicMock:
        actor = MagicMock(name="actor_{0}".format(kwargs["npc"].name))
        actor.npc = kwargs["npc"]
        self.created.append(actor)
        return actor


@allure.story("restore_actors")
@allure.title("restore_actors creates one Actor per NPC and registers each with the Director")
def test_restore_actors_creates_and_registers_actor_per_npc(
    sample_npc,
    populated_graph,
    game_state,
) -> None:
    """restore_actors must create a fresh Actor for every NPC and register it on the Director."""
    second_npc = NPCCard(
        name="Julia",
        biography="A merchant's daughter.",
        occupation="Merchant",
        personality_traits=["sharp"],
        speech_style="terse",
        attributes={"education": 5, "social_status": 5, "strength": 3},
        inventory=[],
        location_id=None,
    )
    game_state.npcs[sample_npc.uuid] = sample_npc
    game_state.npcs[second_npc.uuid] = second_npc

    director = MagicMock()
    recorder = _ActorRecorder()

    with patch("cast.actor.Actor", side_effect=recorder):
        restore_actors(director, game_state, populated_graph, MagicMock(), "English")
        assert len(recorder.created) == 2
        register_calls = director.register_actor.call_args_list
        registered_uuids = {call.args[0] for call in register_calls}
        assert registered_uuids == {sample_npc.uuid, second_npc.uuid}
        for actor in recorder.created:
            actor.set_context.assert_called_once_with(language="English")


@allure.story("restore_actors")
@allure.title("restore_actors is a no-op when game_state.npcs is empty")
def test_restore_actors_noop_on_empty_npcs(populated_graph, game_state) -> None:
    """With no NPCs in state, restore_actors must not create or register anything."""
    director = MagicMock()
    with patch("cast.actor.Actor") as actor_cls:
        restore_actors(director, game_state, populated_graph, MagicMock(), "English")
        actor_cls.assert_not_called()
        director.register_actor.assert_not_called()
