"""Factory helpers that wire LLM clients and the Director agent."""

from __future__ import annotations

import typing

from cast import (
    data_miner as data_miner_mod,
    director as director_mod,
    dramaturge as dramaturge_mod,
    item_generator as item_gen_mod,
    narrator as narrator_mod,
    npc_generator as npc_gen_mod,
    scene_builder as scene_builder_mod,
    world_chronicler as world_chronicler_mod,
)
from cast import anachronism as anachronism_mod
from defaults.models import ModelConfig
from knowledge import graph as graph_mod, memory as memory_mod
from llm.factory import create_llm_client
from models import game_state as gs_mod
from timeline import event_manager as event_manager_mod


class LLMClients(typing.NamedTuple):
    """LLM clients for the engine roles.

    ``dramaturge`` is optional — callers pass ``None`` when the
    consistency-oracle feature flag is off so we never pay to build a
    client we will not use.
    """

    director: typing.Any
    agent: typing.Any
    narrator: typing.Any
    dramaturge: typing.Any | None = None


def create_llm_clients(
    director_model: ModelConfig,
    agent_model: ModelConfig,
    narrator_model: ModelConfig,
    api_keys: dict[str, str | None],
    dramaturge_model: ModelConfig | None = None,
) -> LLMClients:
    """Create LLM clients for director, agent, narrator, and dramaturge roles."""
    dramaturge_client = None
    if dramaturge_model is not None:
        dramaturge_client = create_llm_client(
            dramaturge_model,
            api_key=api_keys.get(dramaturge_model.provider),
        )
    return LLMClients(
        director=create_llm_client(director_model, api_key=api_keys.get(director_model.provider)),
        agent=create_llm_client(agent_model, api_key=api_keys.get(agent_model.provider)),
        narrator=create_llm_client(narrator_model, api_key=api_keys.get(narrator_model.provider)),
        dramaturge=dramaturge_client,
    )


def wire_director(
    clients: LLMClients,
    game_state: gs_mod.GameState,
    event_manager: event_manager_mod.EventManager,
    knowledge_graph: graph_mod.KnowledgeGraph,
    language: str,
    data_miner: typing.Any | None = None,
) -> director_mod.Director:
    """Create the Director with all its agent dependencies.

    When ``clients.dramaturge`` is set, a :class:`Dramaturge` consistency
    oracle is added to the cast; otherwise the dramaturge stays ``None``
    and the PlanExecutor skips the post-Narrator review pass entirely.
    """
    dramaturge: typing.Any | None = None
    if clients.dramaturge is not None:
        dramaturge = dramaturge_mod.Dramaturge(llm_client=clients.dramaturge, language=language)
    return director_mod.Director(
        llm_client=clients.director,
        game_state=game_state,
        event_manager=event_manager,
        memory_manager=memory_mod.MemoryManager(
            graph=knowledge_graph,
            llm_client=clients.agent,
        ),
        scene_builder=scene_builder_mod.SceneBuilder(llm_client=clients.agent, language=language),
        narrator=narrator_mod.Narrator(llm_client=clients.narrator, language=language),
        npc_generator=npc_gen_mod.NPCGenerator(llm_client=clients.agent, language=language),
        data_miner=data_miner or data_miner_mod.DataMiner(llm_client=clients.agent, language=language),
        item_generator=item_gen_mod.ItemGenerator(llm_client=clients.agent, language=language),
        world_chronicler=world_chronicler_mod.WorldChronicler(llm_client=clients.agent, language=language),
        dramaturge=dramaturge,
        anachronism_classifier=anachronism_mod.AnachronismClassifier(llm_client=clients.agent),
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
    from scratch.  Each NPC is also (re-)registered as a graph node so
    memory edges created by the MemoryManager have a valid endpoint,
    even on a freshly rehydrated graph where the NPC node would
    otherwise be missing.
    """
    from cast.actor import Actor
    from knowledge.query import KnowledgeQueryEngine

    for npc_uuid, npc in game_state.npcs.items():
        knowledge_graph.register_actor_node(
            npc_uuid,
            label="{0} ({1})".format(npc.name, npc.occupation),
        )
        actor = Actor(
            llm_client=llm_client,
            npc=npc,
            knowledge_query=KnowledgeQueryEngine(knowledge_graph),
            language=language,
        )
        director.register_actor(npc_uuid, actor)
