"""Factory helpers that wire LLM clients and the Director agent."""

from __future__ import annotations

from typing import Any, NamedTuple

from cast.data_miner import DataMiner
from cast.director import Director, DirectorCast, DirectorDeps
from cast.narrator import Narrator
from cast.npc_generator import NPCGenerator
from cast.scene_builder import SceneBuilder
from defaults.models import ModelConfig
from knowledge.graph import KnowledgeGraph
from knowledge.memory import MemoryManager
from llm.factory import create_llm_client
from models.game_state import GameState
from timeline.event_manager import EventManager


class LLMClients(NamedTuple):
    """LLM clients for the three engine roles."""

    director: Any
    agent: Any
    narrator: Any


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


class DirectorContext(NamedTuple):
    """Runtime context required to build a Director."""

    game_state: GameState
    event_manager: EventManager
    knowledge_graph: KnowledgeGraph


def wire_director(
    clients: LLMClients,
    ctx: DirectorContext,
    language: str,
    data_miner: Any | None = None,
) -> Director:
    """Create the Director with all its agent dependencies."""
    return Director(
        llm_client=clients.director,
        deps=DirectorDeps(
            game_state=ctx.game_state,
            event_manager=ctx.event_manager,
            memory_manager=MemoryManager(
                graph=ctx.knowledge_graph,
                llm_client=clients.agent,
            ),
        ),
        cast=DirectorCast(
            scene_builder=SceneBuilder(llm_client=clients.agent),
            narrator=Narrator(llm_client=clients.narrator, language=language),
            npc_generator=NPCGenerator(llm_client=clients.agent),
            data_miner=data_miner or DataMiner(llm_client=clients.agent),
        ),
        language=language,
    )


def restore_actors(
    director: Director,
    game_state: GameState,
    knowledge_graph: KnowledgeGraph,
    llm_client: Any,
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
