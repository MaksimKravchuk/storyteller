"""Factory helpers that wire LLM clients and the Director agent."""

from __future__ import annotations

import typing

from cast import data_miner as data_miner_mod, director as director_mod
from cast import narrator as narrator_mod, npc_generator as npc_gen_mod, scene_builder as scene_builder_mod
from defaults.models import ModelConfig
from knowledge import graph as graph_mod, memory as memory_mod
from llm.factory import create_llm_client
from models import game_state as gs_mod
from timeline import event_manager as event_manager_mod


class LLMClients(typing.NamedTuple):
    """LLM clients for the three engine roles."""

    director: typing.Any
    agent: typing.Any
    narrator: typing.Any


def create_llm_clients(
    director_model: ModelConfig,
    agent_model: ModelConfig,
    narrator_model: ModelConfig,
    api_keys: dict[str, str | None],
) -> LLMClients:
    """Create LLM clients for director, agent, and narrator roles."""
    return LLMClients(
        director=create_llm_client(director_model, api_key=api_keys.get(director_model.provider)),
        agent=create_llm_client(agent_model, api_key=api_keys.get(agent_model.provider)),
        narrator=create_llm_client(narrator_model, api_key=api_keys.get(narrator_model.provider)),
    )


class DirectorContext(typing.NamedTuple):
    """Runtime context required to build a Director."""

    game_state: gs_mod.GameState
    event_manager: event_manager_mod.EventManager
    knowledge_graph: graph_mod.KnowledgeGraph


def wire_director(
    clients: LLMClients,
    ctx: DirectorContext,
    language: str,
    data_miner: typing.Any | None = None,
) -> director_mod.Director:
    """Create the Director with all its agent dependencies."""
    return director_mod.Director(
        llm_client=clients.director,
        deps=director_mod.DirectorDeps(
            game_state=ctx.game_state,
            event_manager=ctx.event_manager,
            memory_manager=memory_mod.MemoryManager(
                graph=ctx.knowledge_graph,
                llm_client=clients.agent,
            ),
        ),
        cast=director_mod.DirectorCast(
            scene_builder=scene_builder_mod.SceneBuilder(llm_client=clients.agent),
            narrator=narrator_mod.Narrator(llm_client=clients.narrator, language=language),
            npc_generator=npc_gen_mod.NPCGenerator(llm_client=clients.agent),
            data_miner=data_miner or data_miner_mod.DataMiner(llm_client=clients.agent),
        ),
        language=language,
    )


def restore_actors(
    director: director_mod.Director,
    game_state: gs_mod.GameState,
    knowledge_graph: graph_mod.KnowledgeGraph,
    llm_client: typing.Any,
    language: str,
) -> None:
    """Recreate Actor agents for every NPC already present in game state.

    Called during ``restore_session`` so that NPCs initialised in prior
    turns get working Actor agents even though the engine was rebuilt
    from scratch.
    """
    from cast.actor import Actor
    from knowledge.query import KnowledgeQueryEngine

    for npc_uuid, npc in game_state.npcs.items():
        actor = Actor(
            llm_client=llm_client,
            npc=npc,
            knowledge_query=KnowledgeQueryEngine(knowledge_graph),
        )
        actor.set_context(language=language)
        director.register_actor(npc_uuid, actor)
