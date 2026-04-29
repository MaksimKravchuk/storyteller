"""Game Engine — top-level public API for the text quest."""

from __future__ import annotations

from cast.data_miner import DataMiner
from cast.director import Director
from defaults.models import AI_MODELS, ModelConfig
from engine.engine_wiring import LLMClients, create_llm_clients, restore_actors, wire_director
from engine.graph_populator import populate_graph_from_setting
from knowledge.graph import KnowledgeGraph
from models.game_state import GameState
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
        director_model: ModelConfig = AI_MODELS.gpt5_4_mini,
        agent_model: ModelConfig = AI_MODELS.gpt5_4_nano,
        narrator_model: ModelConfig = AI_MODELS.gpt5_4_mini,
        dramaturge_model: ModelConfig | None = None,
        api_keys: dict[str, str | None] | None = None,
        language: str = "English",
    ):
        self._director_model = director_model
        self._agent_model = agent_model
        self._narrator_model = narrator_model
        self._dramaturge_model = dramaturge_model
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
        clients = self._make_clients()

        data_miner = DataMiner(llm_client=clients.agent, language=self._language)
        setting = await data_miner.execute(setting_description)

        self._knowledge_graph = KnowledgeGraph()
        populate_graph_from_setting(self._knowledge_graph, setting)
        self._game_state = GameState(setting=setting, knowledge_graph=self._knowledge_graph)
        self._event_manager = EventManager(game_state=self._game_state, knowledge_graph=self._knowledge_graph)

        self._director = wire_director(
            clients,
            self._game_state,
            self._event_manager,
            self._knowledge_graph,
            self._language,
            data_miner,
        )
        return await self._director.execute("Look around and describe the starting scene")

    async def process_action(self, player_action: str) -> str:
        """Process a player action and return the narrated response."""
        if not self._director:
            raise RuntimeError("Game not started. Call start_game() first.")
        return await self._director.execute(player_action)

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

        clients = self._make_clients()
        self._director = wire_director(
            clients,
            self._game_state,
            self._event_manager,
            self._knowledge_graph,
            self._language,
        )
        restore_actors(self._director, self._game_state, self._knowledge_graph, clients.agent, self._language)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _make_clients(self) -> LLMClients:
        """Build LLM clients from stored model configs."""
        return create_llm_clients(
            self._director_model,
            self._agent_model,
            self._narrator_model,
            self._api_keys,
            dramaturge_model=self._dramaturge_model,
        )
