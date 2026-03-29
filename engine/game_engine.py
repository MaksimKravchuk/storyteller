"""Game Engine — top-level public API for the text quest."""

from __future__ import annotations

from typing import Any

from cast.data_miner import DataMiner
from cast.director import Director
from cast.narrator import Narrator
from cast.npc_generator import NPCGenerator
from cast.scene_builder import SceneBuilder
from defaults.models import AI_MODELS, ModelConfig
from knowledge.graph import KnowledgeGraph
from knowledge.memory import MemoryManager
from knowledge.node import KnowledgeNode, KnowledgeScope, KnowledgeSource
from llm.factory import create_llm_client
from models.game_state import GameState
from models.setting import Setting
from timeline.event import GameEvent
from timeline.event_manager import EventManager


class GameEngine:
    """Top-level API for the Storyteller text quest engine.

    Usage::

        engine = GameEngine()
        opening = await engine.start_game(
            "Medieval Florence, 1480s, during the reign of Lorenzo de Medici"
        )
        print(opening)

        while True:
            action = input("> ")
            response = await engine.process_action(action)
            print(response)
    """

    def __init__(
        self,
        *,
        director_model: ModelConfig = AI_MODELS.gpt_4,
        agent_model: ModelConfig = AI_MODELS.gpt_3_5_turbo,
        narrator_model: ModelConfig = AI_MODELS.gpt_4,
        api_keys: dict[str, str | None] | None = None,
        language: str = "English",
    ):
        self._director_model = director_model
        self._agent_model = agent_model
        self._narrator_model = narrator_model
        self._api_keys: dict[str, str | None] = api_keys or {}
        self._language = language

        self._director: Director | None = None
        self._game_state: GameState | None = None
        self._knowledge_graph: KnowledgeGraph | None = None
        self._event_manager: EventManager | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start_game(self, setting_description: str) -> str:
        """Initialise a new game session.

        1. Data Miner researches the setting via Wikipedia.
        2. Knowledge graph is populated with setting data.
        3. Event manager is created.
        4. All agents are wired together.
        5. An opening scene is generated.

        Returns the opening narration.
        """
        # Create LLM clients (pass the right API key per provider)
        director_llm = create_llm_client(
            self._director_model,
            api_key=self._api_keys.get(self._director_model.provider),
        )
        agent_llm = create_llm_client(
            self._agent_model,
            api_key=self._api_keys.get(self._agent_model.provider),
        )
        narrator_llm = create_llm_client(
            self._narrator_model,
            api_key=self._api_keys.get(self._narrator_model.provider),
        )

        # Research the setting
        data_miner = DataMiner(llm_client=agent_llm)
        setting = await data_miner.execute(setting_description)

        # Initialise knowledge graph
        self._knowledge_graph = KnowledgeGraph()
        self._populate_graph_from_setting(setting)

        # Initialise game state
        self._game_state = GameState(
            setting=setting,
            knowledge_graph=self._knowledge_graph,
        )

        # Memory manager (for summarising interactions / events)
        memory_manager = MemoryManager(
            graph=self._knowledge_graph,
            llm_client=agent_llm,
        )

        # Event manager
        self._event_manager = EventManager(
            game_state=self._game_state,
            knowledge_graph=self._knowledge_graph,
        )

        # Create agents
        scene_builder = SceneBuilder(llm_client=agent_llm)
        npc_generator = NPCGenerator(llm_client=agent_llm)
        narrator = Narrator(llm_client=narrator_llm, language=self._language)

        # Create the Director — wires everything together
        self._director = Director(
            llm_client=director_llm,
            game_state=self._game_state,
            event_manager=self._event_manager,
            memory_manager=memory_manager,
            scene_builder=scene_builder,
            narrator=narrator,
            npc_generator=npc_generator,
            data_miner=data_miner,
            language=self._language,
        )

        # Generate opening scene
        opening = await self._director.execute("Look around and describe the starting scene")
        return opening

    async def process_action(self, player_action: str) -> str:
        """Process a player action and return the narrated response."""
        if not self._director:
            raise RuntimeError("Game not started. Call start_game() first.")
        return await self._director.execute(player_action)

    def schedule_event(self, event: GameEvent) -> str:
        """Schedule a world or NPC event on the timeline."""
        if not self._event_manager:
            raise RuntimeError("Game not started.")
        return self._event_manager.schedule(event)

    def get_game_time(self) -> float:
        """Return the current game clock in hours."""
        if not self._game_state:
            return 0.0
        return self._game_state.game_clock

    @property
    def game_state(self) -> GameState | None:
        """Access the current game state for inspection."""
        return self._game_state

    @property
    def knowledge_graph(self) -> KnowledgeGraph | None:
        return self._knowledge_graph

    @property
    def event_manager(self) -> EventManager | None:
        return self._event_manager

    async def restore_session(
        self,
        game_state: GameState,
        knowledge_graph: KnowledgeGraph,
        events: list[GameEvent],
    ) -> None:
        """Restore a game session from previously saved state.

        Wires up all agents using the provided state objects instead of
        calling ``start_game()``.
        """
        self._game_state = game_state
        self._knowledge_graph = knowledge_graph

        # Create LLM clients
        director_llm = create_llm_client(
            self._director_model,
            api_key=self._api_keys.get(self._director_model.provider),
        )
        agent_llm = create_llm_client(
            self._agent_model,
            api_key=self._api_keys.get(self._agent_model.provider),
        )
        narrator_llm = create_llm_client(
            self._narrator_model,
            api_key=self._api_keys.get(self._narrator_model.provider),
        )

        # Memory manager
        memory_manager = MemoryManager(
            graph=self._knowledge_graph,
            llm_client=agent_llm,
        )

        # Event manager (restore events)
        self._event_manager = EventManager(
            game_state=self._game_state,
            knowledge_graph=self._knowledge_graph,
        )
        self._event_manager.all_events = events

        # Create agents
        data_miner = DataMiner(llm_client=agent_llm)
        scene_builder = SceneBuilder(llm_client=agent_llm)
        npc_generator = NPCGenerator(llm_client=agent_llm)
        narrator = Narrator(llm_client=narrator_llm, language=self._language)

        # Create the Director
        self._director = Director(
            llm_client=director_llm,
            game_state=self._game_state,
            event_manager=self._event_manager,
            memory_manager=memory_manager,
            scene_builder=scene_builder,
            narrator=narrator,
            npc_generator=npc_generator,
            data_miner=data_miner,
            language=self._language,
        )

        # Restore Actor agents for NPCs that were already initialised in
        # previous turns.  Without this, self.actors is empty after engine
        # recreation (e.g. between Telegram messages) and dialogue routing
        # silently produces no output.
        self._restore_actors(agent_llm)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _restore_actors(self, llm_client: Any) -> None:
        """Recreate Actor agents for every NPC already present in game state.

        Called during ``restore_session`` so that NPCs initialised in prior
        turns get working Actor agents even though the engine was rebuilt
        from scratch.
        """
        from cast.actor import Actor
        from knowledge.query import KnowledgeQueryEngine

        if not self._director or not self._game_state or not self._knowledge_graph:
            return

        for npc_uuid, npc in self._game_state.npcs.items():
            actor = Actor(
                llm_client=llm_client,
                npc=npc,
                knowledge_query=KnowledgeQueryEngine(self._knowledge_graph),
            )
            actor.set_context(language=self._language)
            self._director.register_actor(npc_uuid, actor)

    def _populate_graph_from_setting(self, setting: Setting) -> None:
        """Convert Setting data into knowledge graph nodes."""
        graph = self._knowledge_graph
        if not graph:
            return

        # Setting summary as a world-level fact
        summary_node = KnowledgeNode(
            content=setting.summary,
            scope=KnowledgeScope.WORLD,
            source=KnowledgeSource.FACT,
            tags=["setting", "overview"],
        )
        graph.add_node(summary_node)

        # Key persons
        for person in setting.key_persons:
            node = KnowledgeNode(
                content=(f"{person.get('name', 'Unknown')}: {person.get('role', '')}. {person.get('description', '')}"),
                scope=KnowledgeScope.COUNTRY,
                source=KnowledgeSource.FACT,
                required_education=3,  # Need some education to know political figures
                tags=["person", "politics"],
            )
            graph.add_node(node)

        # Key events
        for event in setting.key_events:
            node = KnowledgeNode(
                content=(
                    f"{event.get('name', 'Unknown event')} ({event.get('date', '')}): {event.get('description', '')}"
                ),
                scope=KnowledgeScope.REGION,
                source=KnowledgeSource.FACT,
                required_education=2,
                tags=["event", "history"],
            )
            graph.add_node(node)

        # Locations
        for loc in setting.locations:
            node = KnowledgeNode(
                content=(f"{loc.get('name', 'Unknown place')} ({loc.get('type', '')}): {loc.get('description', '')}"),
                scope=KnowledgeScope.CITY,
                source=KnowledgeSource.FACT,
                tags=["location"],
            )
            graph.add_node(node)

        # Traditions — common knowledge
        for tradition in setting.traditions:
            node = KnowledgeNode(
                content=tradition,
                scope=KnowledgeScope.REGION,
                source=KnowledgeSource.FACT,
                required_education=0,  # Everyone knows local traditions
                tags=["tradition", "culture"],
            )
            graph.add_node(node)

        # Technologies
        for tech in setting.technologies:
            node = KnowledgeNode(
                content=tech,
                scope=KnowledgeScope.REGION,
                source=KnowledgeSource.FACT,
                required_education=1,
                tags=["technology"],
            )
            graph.add_node(node)

        # Social structure
        if setting.social_structure:
            node = KnowledgeNode(
                content=setting.social_structure,
                scope=KnowledgeScope.COUNTRY,
                source=KnowledgeSource.FACT,
                required_education=2,
                tags=["society", "social_structure"],
            )
            graph.add_node(node)
