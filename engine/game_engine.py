"""Game Engine — top-level public API for the text quest."""

from __future__ import annotations

from dataclasses import dataclass

from cast.data_miner import DataMiner
from cast.director import Director
from defaults.models import AI_MODELS, ModelConfig
from engine.engine_wiring import DirectorContext, create_llm_clients, restore_actors, wire_director
from engine.graph_populator import populate_graph_from_setting
from knowledge.graph import KnowledgeGraph
from models.game_state import GameState
from timeline.event import GameEvent
from timeline.event_manager import EventManager


@dataclass(frozen=True)
class EngineModels:
    """Bundle of per-role LLM model configs for a :class:`GameEngine`.

    The four roles (director, agent, narrator, dramaturge) always
    travel together: every engine needs all four resolved from the
    same :class:`Config` and threaded through the same
    :func:`create_llm_clients` call. Bundling them here makes that
    grouping explicit and keeps :meth:`GameEngine.__init__` within
    its argument budget as a side benefit. ``dramaturge`` defaults
    to ``None`` because the consistency-oracle feature flag is off
    by default, so we do not resolve a model for it unless the
    caller explicitly requests it.
    """

    director: ModelConfig = AI_MODELS.gpt5_4_mini
    agent: ModelConfig = AI_MODELS.gpt5_4_nano
    narrator: ModelConfig = AI_MODELS.gpt5_4_mini
    dramaturge: ModelConfig | None = None


_DEFAULT_MODELS = EngineModels()


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
        models: EngineModels = _DEFAULT_MODELS,
        api_keys: dict[str, str | None] | None = None,
        language: str = "English",
    ):
        self._models = models
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
        clients = create_llm_clients(
            self._models.director,
            self._models.agent,
            self._models.narrator,
            self._api_keys,
            dramaturge_model=self._models.dramaturge,
        )

        data_miner = DataMiner(llm_client=clients.agent, language=self._language)
        setting = await data_miner.execute(setting_description)

        self._knowledge_graph = KnowledgeGraph()
        populate_graph_from_setting(self._knowledge_graph, setting)
        self._game_state = GameState(setting=setting, knowledge_graph=self._knowledge_graph)
        self._event_manager = EventManager(game_state=self._game_state, knowledge_graph=self._knowledge_graph)

        ctx = DirectorContext(self._game_state, self._event_manager, self._knowledge_graph)
        self._director = wire_director(clients, ctx, self._language, data_miner)
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

        clients = create_llm_clients(
            self._models.director,
            self._models.agent,
            self._models.narrator,
            self._api_keys,
            dramaturge_model=self._models.dramaturge,
        )
        ctx = DirectorContext(self._game_state, self._event_manager, self._knowledge_graph)
        self._director = wire_director(clients, ctx, self._language)
        restore_actors(self._director, self._game_state, self._knowledge_graph, clients.agent, self._language)
