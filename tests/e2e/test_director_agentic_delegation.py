"""Real-model Director delegation smoke tests."""

from __future__ import annotations

import functools
from unittest import mock

import allure
import pytest

import config as config_mod
from cast import director as director_mod
from knowledge import memory as memory_mod
from llm import factory as llm_factory
from models import npc_card as npc_mod, scene as scene_mod
from tests import _uuid_helpers as uuid_helpers, actor_helpers, director_helpers
from timeline import event_manager as event_manager_mod

_GUARD_ID = uuid_helpers.make_uuid("agentic-guard")
_MESSENGER_ID = uuid_helpers.make_uuid("agentic-lucius")
_FORUM_ID = uuid_helpers.make_uuid("agentic-forum")
_KEY_NPC_GENERATOR = "npc_generator"
_KEY_NARRATOR = "narrator"


def _real_director_llm():
    """Create the configured Director LLM client, or skip when credentials are absent."""
    config = config_mod.load_config()
    model_config = config_mod.resolve_model_config(config.director_model)
    api_key = config_mod.get_api_key_for_provider(model_config.provider, config)
    if not api_key:
        pytest.skip("No Director LLM API key configured — skipping real-model delegation smoke test")
    return llm_factory.create_llm_client(model_config, api_key=api_key)


def _make_spy_director(game_state, cast):
    """Build a Director with a real router LLM and mocked performer agents."""
    return director_mod.Director(
        llm_client=_real_director_llm(),
        game_state=game_state,
        event_manager=event_manager_mod.EventManager(game_state=game_state, knowledge_graph=game_state.knowledge_graph),
        memory_manager=mock.MagicMock(spec=memory_mod.MemoryManager),
        scene_builder=cast["scene_builder"],
        narrator=cast[_KEY_NARRATOR],
        npc_generator=cast[_KEY_NPC_GENERATOR],
        data_miner=cast["data_miner"],
        item_generator=cast["item_generator"],
        language="English",
    )


def _npc_generator(cast):
    """Return the NPC generator spy from a cast dict."""
    return cast[_KEY_NPC_GENERATOR]


def _npc_card(name: str, occupation: str, uuid=None) -> npc_mod.NPCCard:
    """Create a stable NPC card returned by mocked downstream agents."""
    npc = npc_mod.NPCCard(name=name, occupation=occupation)
    slug = name.lower().replace(" ", "-")
    npc.uuid = uuid or uuid_helpers.make_uuid("agentic-{0}".format(slug))
    npc.current_mood = "neutral"
    return npc


def _mock_actor(*replies: str) -> mock.AsyncMock:
    """Create an actor spy that returns the supplied reply texts in order."""
    actor = mock.AsyncMock()
    side_effect = []
    for reply in replies:
        side_effect.append(actor_helpers.actor_reply(text=reply))
    actor.execute = mock.AsyncMock(side_effect=side_effect)
    return actor


def _register_mock_actor(npc: npc_mod.NPCCard, director: director_mod.Director, actor: mock.AsyncMock) -> None:
    """Register an NPC and wire a mock actor instead of constructing a real Actor."""
    director._game_state.npcs[npc.uuid] = npc
    director._actors[npc.uuid] = actor


@allure.epic("AI Agent Orchestration")
@allure.feature("Director real-model delegation")
class TestDirectorRealModelDelegation:
    @allure.story("Known NPC routing")
    @allure.title("A real Director model routes a guard conversation to the Actor and Narrator")
    @pytest.mark.asyncio
    async def test_real_model_talks_to_known_npc_actor(self):
        game_state = director_helpers.make_game_state()
        guard = _npc_card("Marcus", "forum guard")
        guard.uuid = _GUARD_ID
        game_state.npcs[_GUARD_ID] = guard
        game_state.current_scene = scene_mod.Scene(
            location_id=_FORUM_ID,
            description="A quiet Roman forum with a fountain and market stalls.",
            npcs_present=[scene_mod.SceneNPC(role="forum guard", uuid=_GUARD_ID)],
            points_of_interest=[],
        )

        cast = director_helpers.make_cast()
        _npc_generator(cast).execute = mock.AsyncMock(return_value=[])
        director = _make_spy_director(game_state, cast)
        actor = _mock_actor(
            "The guard nods cautiously.",
            '{"action":"The guard resumes his watch.","type":"IDLE","target":null}',
        )
        director._actors[_GUARD_ID] = actor

        await director.act("Ask the forum guard whether he has seen any suspicious strangers.")

        actor.execute.assert_awaited()
        cast[_KEY_NARRATOR].execute.assert_awaited_once()
        _npc_generator(cast).execute.assert_not_awaited()

    @allure.story("Unknown NPC materialisation")
    @allure.title("A real Director model talking to an uninitialised scene NPC invokes the NPC generator")
    @pytest.mark.xfail(
        strict=False,
        reason=(
            "Known model nondeterminism: ``gpt-5.4-mini`` Director occasionally "
            "decides to skip NPCGenerator and dispatch the SceneNPC straight to "
            "Actor instead. Confirmed against ``origin/main`` independently of "
            "the matrix-selector PR. ``strict=False`` so the test surfaces the "
            "signal (XFAIL/XPASS) without blocking CI; flip to a hard assertion "
            "once the routing prompt's NPC-materialisation guard is tightened."
        ),
    )
    @pytest.mark.asyncio
    async def test_real_model_calls_npc_generator(self):
        game_state = director_helpers.make_game_state()
        game_state.current_scene = scene_mod.Scene(
            location_id=_FORUM_ID,
            description="A quiet Roman forum with a fountain and market stalls.",
            npcs_present=[scene_mod.SceneNPC(role="wounded messenger")],
            points_of_interest=[],
        )

        cast = director_helpers.make_cast()
        _npc_generator(cast).execute = mock.AsyncMock(
            return_value=[_npc_card("Lucius", "wounded messenger", uuid=_MESSENGER_ID)],
        )
        director = _make_spy_director(game_state, cast)
        actor = _mock_actor(
            "The messenger asks for water before speaking.",
            '{"action":"The messenger clutches his side.","type":"IDLE","target":null}',
        )
        director._executor._register_npc = functools.partial(_register_mock_actor, director=director, actor=actor)

        await director.act("Ask the wounded messenger what happened on the road.")

        _npc_generator(cast).execute.assert_awaited_once()
        assert _npc_generator(cast).execute.await_args is not None
        call_kwargs = _npc_generator(cast).execute.await_args.kwargs
        assert call_kwargs["input_data"] == ["wounded messenger"]
        assert game_state.current_scene is not None
        assert game_state.current_scene.npcs_present[0].uuid == _MESSENGER_ID
        actor.execute.assert_awaited()
        cast[_KEY_NARRATOR].execute.assert_awaited_once()
