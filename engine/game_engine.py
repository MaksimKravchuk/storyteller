"""Game Engine — top-level public API for the text quest."""

from __future__ import annotations

from typing import Any

from cast.data_miner import DataMiner
from cast.director import Director, DirectorCast, DirectorDeps
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


def _format_person_content(person: dict) -> str:
    name = person.get("name", "Unknown")
    role = person.get("role", "")
    description = person.get("description", "")
    return f"{name}: {role}. {description}"


def _format_event_content(event: dict) -> str:
    name = event.get("name", "Unknown event")
    date = event.get("date", "")
    description = event.get("description", "")
    return f"{name} ({date}): {description}"


def _format_location_content(loc: dict) -> str:
    name = loc.get("name", "Unknown place")
    loc_type = loc.get("type", "")
    description = loc.get("description", "")
    return f"{name} ({loc_type}): {description}"


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
        director_model: ModelConfig = AI_MODELS.gpt4,
        agent_model: ModelConfig = AI_MODELS.gpt35_turbo,
        narrator_model: ModelConfig = AI_MODELS.gpt4,
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
        director_llm, agent_llm, narrator_llm = self._create_llm_clients()

        data_miner = DataMiner(llm_client=agent_llm)
        setting = await data_miner.execute(setting_description)

        self._knowledge_graph = KnowledgeGraph()
        self._populate_graph_from_setting(setting)
        self._game_state = GameState(setting=setting, knowledge_graph=self._knowledge_graph)
        self._event_manager = EventManager(game_state=self._game_state, knowledge_graph=self._knowledge_graph)

        self._wire_director(director_llm, agent_llm, narrator_llm, data_miner)
        return await self._director.execute("Look around and describe the starting scene")  # type: ignore[union-attr]

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
            return float(0)
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
        self._event_manager = EventManager(game_state=self._game_state, knowledge_graph=self._knowledge_graph)
        self._event_manager.all_events = events

        director_llm, agent_llm, narrator_llm = self._create_llm_clients()
        self._wire_director(director_llm, agent_llm, narrator_llm)
        self._restore_actors(agent_llm)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _create_llm_clients(self) -> tuple[Any, Any, Any]:
        """Create LLM clients for director, agent, and narrator roles."""
        return (
            create_llm_client(self._director_model, api_key=self._api_keys.get(self._director_model.provider)),
            create_llm_client(self._agent_model, api_key=self._api_keys.get(self._agent_model.provider)),
            create_llm_client(self._narrator_model, api_key=self._api_keys.get(self._narrator_model.provider)),
        )

    def _wire_director(
        self,
        director_llm: Any,
        agent_llm: Any,
        narrator_llm: Any,
        data_miner: Any | None = None,
    ) -> None:
        """Create the Director with all its agent dependencies."""
        self._director = Director(
            llm_client=director_llm,
            deps=DirectorDeps(
                game_state=self._game_state,  # type: ignore[arg-type]
                event_manager=self._event_manager,  # type: ignore[arg-type]
                memory_manager=MemoryManager(
                    graph=self._knowledge_graph,  # type: ignore[arg-type]
                    llm_client=agent_llm,
                ),
            ),
            cast=DirectorCast(
                scene_builder=SceneBuilder(llm_client=agent_llm),
                narrator=Narrator(llm_client=narrator_llm, language=self._language),
                npc_generator=NPCGenerator(llm_client=agent_llm),
                data_miner=data_miner or DataMiner(llm_client=agent_llm),
            ),
            language=self._language,
        )

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
        if not self._knowledge_graph:
            return

        self._knowledge_graph.add_node(
            KnowledgeNode(
                content=setting.summary,
                scope=KnowledgeScope.WORLD,
                source=KnowledgeSource.FACT,
                tags=["setting", "overview"],
            )
        )
        self._add_persons_and_events(setting)
        self._add_locations_and_culture(setting)

    def _add_persons_and_events(self, setting: Setting) -> None:
        """Add key persons and events from setting to knowledge graph."""
        for person in setting.key_persons:
            self._add_setting_node(
                self._knowledge_graph,
                _format_person_content(person),
                KnowledgeScope.COUNTRY,
                required_education=3,
                tags=["person", "politics"],
            )
        for event in setting.key_events:
            self._add_setting_node(
                self._knowledge_graph,
                _format_event_content(event),
                KnowledgeScope.REGION,
                required_education=2,
                tags=["event", "history"],
            )

    def _add_locations_and_culture(self, setting: Setting) -> None:
        """Add locations, traditions, technologies, and social structure."""
        for loc in setting.locations:
            self._add_setting_node(
                self._knowledge_graph,
                _format_location_content(loc),
                KnowledgeScope.CITY,
                tags=["location"],
            )
        for tradition in setting.traditions:
            self._add_setting_node(
                self._knowledge_graph, tradition, KnowledgeScope.REGION, tags=["tradition", "culture"]
            )
        for tech in setting.technologies:
            self._add_setting_node(
                self._knowledge_graph,
                tech,
                KnowledgeScope.REGION,
                required_education=1,
                tags=["technology"],
            )
        if setting.social_structure:
            self._add_setting_node(
                self._knowledge_graph,
                setting.social_structure,
                KnowledgeScope.COUNTRY,
                required_education=2,
                tags=["society", "social_structure"],
            )

    def _add_setting_node(
        self,
        graph: KnowledgeGraph | None,
        node_content: str,
        scope: KnowledgeScope,
        required_education: int = 0,
        tags: list[str] | None = None,
    ) -> None:
        """Add a FACT knowledge node to the graph."""
        if not graph:
            return
        graph.add_node(
            KnowledgeNode(
                content=node_content,
                scope=scope,
                source=KnowledgeSource.FACT,
                required_education=required_education,
                tags=tags or [],
            )
        )
