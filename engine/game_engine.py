"""Game Engine — top-level public API for the text quest."""

from __future__ import annotations

from cast.data_miner import DataMiner
from cast.director import Director
from defaults.models import AI_MODELS, ModelConfig
from engine import graph_populator, location_init
from engine.engine_wiring import LLMClients, create_llm_clients, restore_actors, wire_director
from engine.moderation import Moderator, moderate_input, moderate_output
from knowledge.graph import KnowledgeGraph
from models.game_state import GameState, PlayerState
from models.player_character_input import PlayerCharacterInput
from research.base_search_client import BaseSearchClient
from timeline import event as event_mod, event_manager as event_manager_mod

_OPENING_SCENE_PROMPT = (
    "Look around and describe the starting scene. For any premise involving social investigation, rumor-gathering, "
    "bargaining, testimony, or asking locals for information, include at least one named, addressable NPC or an "
    "explicit immediate path to one, with a visible social affordance the player can act on."
)


def _apply_character_to_player(player: PlayerState, character: PlayerCharacterInput) -> None:
    """Apply onboarding character to player; blank name keeps anonymous default."""
    if character.name:
        player.name = character.name
    player.appearance = character.appearance
    player.inventory = list(character.inventory)
    player.origin_era = character.origin_era


def _hide_opening_prompt_from_player_history(game_state: GameState) -> None:
    """Keep the internal opening-scene prompt out of player-visible turn history."""
    if not game_state.conversation_log:
        return
    opening_entry = game_state.conversation_log[-1]
    if opening_entry.get("player_action") != _OPENING_SCENE_PROMPT:
        return
    opening_entry.pop("player_action", None)
    opening_entry["turn"] = 0
    game_state.turn_count = 0
    game_state.round_number = 0
    if _scene_log_matches_opening_prompt(game_state):
        game_state.scene_conversation_log.pop()


def _scene_log_matches_opening_prompt(game_state: GameState) -> bool:
    """Return true when the newest scene-history row is the synthetic opening prompt."""
    if not game_state.scene_conversation_log:
        return False
    return game_state.scene_conversation_log[-1].get("player_action") == _OPENING_SCENE_PROMPT


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
        moderator: Moderator | None = None,
        search_client: "BaseSearchClient | None" = None,
    ):
        self._director_model = director_model
        self._agent_model = agent_model
        self._narrator_model = narrator_model
        self._dramaturge_model = dramaturge_model
        self._api_keys: dict[str, str | None] = api_keys or {}
        self._language = language
        self._moderator = moderator
        self._search_client = search_client

        self._director: Director | None = None
        self._game_state: GameState | None = None
        self._knowledge_graph: KnowledgeGraph | None = None
        self._event_manager: event_manager_mod.EventManager | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start_game(
        self,
        setting_description: str,
        character: PlayerCharacterInput | None = None,
    ) -> str:
        """Initialise a new game session.

        1. Data Miner researches the setting via Wikipedia.
        2. Knowledge graph is populated with setting data.
        3. Event manager is created.
        4. All agents are wired together.
        5. An opening scene is generated.

        ``character`` populates the player's name, appearance, and
        starting inventory; omitting it keeps anonymous defaults so
        callers that don't yet collect onboarding info still work.

        Returns the opening narration.
        """
        clients = self._make_clients()

        data_miner = DataMiner(
            llm_client=clients.agent,
            language=self._language,
            search_client=self._search_client,
        )
        setting = await data_miner.execute(setting_description)

        self._knowledge_graph = KnowledgeGraph()
        graph_populator.populate_graph_from_setting(self._knowledge_graph, setting)
        self._game_state = GameState(setting=setting, knowledge_graph=self._knowledge_graph)
        location_init.materialise_setting_locations(self._game_state)
        if character is not None:
            _apply_character_to_player(self._game_state.player, character)
        self._event_manager = event_manager_mod.EventManager(
            game_state=self._game_state,
            knowledge_graph=self._knowledge_graph,
        )

        self._director = wire_director(
            clients,
            self._game_state,
            self._event_manager,
            self._knowledge_graph,
            self._language,
            data_miner,
        )
        opening_narration = await self._director.execute(_OPENING_SCENE_PROMPT, context={"opening": True})
        _hide_opening_prompt_from_player_history(self._game_state)
        return opening_narration

    async def process_action(self, player_action: str) -> str:
        """Process a player action and return the narrated response.

        When a :class:`Moderator` is wired, ``player_action`` is checked
        before it reaches the Director — a flagged action raises
        :class:`safety.moderator.SafetyRejectedError`. The narrator's prose
        is then checked on the way back out; if that response is flagged,
        the original is suppressed and a safe-fallback string is returned.
        """
        if not self._director:
            raise RuntimeError("Game not started. Call start_game() first.")
        await moderate_input(self._moderator, player_action)
        narration = await self._director.execute(player_action)
        return await moderate_output(self._moderator, narration)

    def assert_running(self) -> tuple[GameState, KnowledgeGraph, event_manager_mod.EventManager]:
        """Return (game_state, knowledge_graph, event_manager), raising if not started."""
        if self._game_state is None or self._knowledge_graph is None or self._event_manager is None:
            raise RuntimeError("Game not started. Call start_game() first.")
        return self._game_state, self._knowledge_graph, self._event_manager

    async def restore_session(
        self,
        game_state: GameState,
        knowledge_graph: KnowledgeGraph,
        events: list[event_mod.GameEvent],
    ) -> None:
        """Restore a game session from previously saved state.

        Wires up all agents using the provided state objects instead of
        calling ``start_game()``.
        """
        self._game_state = game_state
        self._knowledge_graph = knowledge_graph
        self._event_manager = event_manager_mod.EventManager(
            game_state=self._game_state,
            knowledge_graph=self._knowledge_graph,
        )
        self._event_manager.all_events = events

        clients = self._make_clients()
        self._director = wire_director(
            clients,
            self._game_state,
            self._event_manager,
            self._knowledge_graph,
            self._language,
            search_client=self._search_client,
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
