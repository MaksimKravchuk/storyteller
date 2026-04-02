"""Director — central orchestrator of the text quest engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from cast.base_performer_class import BasePerformer
from cast.director_context import ContextFormatter
from cast.director_dialogue import DialogueHandler
from cast.director_events import EventProcessor
from cast.director_execution import PlanExecutor, _Agents
from cast.director_retaliation import RetaliationHandler
from cast.director_routing import ActionRouter
from knowledge.memory import MemoryManager
from models.game_state import GameState
from prompts.director_prompts import DIRECTOR_SYSTEM
from timeline.event import GameEvent
from timeline.event_manager import EventManager

_KEY_ACTION_TYPE = "action_type"
_DEFAULT_ACTION = "OTHER"

# Actions that increment the turn counter.
TURN_COUNTING_ACTIONS: frozenset[str] = frozenset(("EXPLORE", "MOVE", "INTERACT", "TALK", "SLEEP"))

# Actions that trigger a scene rebuild (new location, time-of-day shift, etc.).
SCENE_CHANGING_ACTIONS: frozenset[str] = frozenset(("EXPLORE", "MOVE", "SLEEP"))


@dataclass
class DirectorDeps:
    """Runtime dependencies the Director needs to orchestrate the game."""

    game_state: GameState
    event_manager: EventManager
    memory_manager: MemoryManager


@dataclass
class DirectorCast:
    """The ensemble of specialist agents the Director delegates to."""

    scene_builder: Any
    narrator: Any
    npc_generator: Any
    data_miner: Any
    actors: dict[str, Any] = field(default_factory=dict)


class Director(BasePerformer):
    """Central orchestrator.

    Receives player input, classifies the action, advances game time,
    resolves completed events, delegates to specialist agents, and
    passes everything through the Narrator for final output.
    """

    def __init__(
        self,
        *,
        llm_client: Any,
        deps: DirectorDeps,
        cast: DirectorCast,
        language: str = "English",
    ):
        super().__init__(
            llm_client=llm_client,
            system_prompt_template=DIRECTOR_SYSTEM,
        )
        self._deps = deps
        self._cast = cast
        self._actors: dict[str, Any] = dict(cast.actors)
        self._language = language

        self._ctx = ContextFormatter(deps.game_state)
        self._router = ActionRouter(deps.game_state, self._send_json)
        self._events = EventProcessor(deps.game_state, deps.event_manager, deps.memory_manager)
        self._dialogue = DialogueHandler(deps.game_state, self._actors)
        self._retaliation = RetaliationHandler(deps.game_state, self._actors)
        agents = _Agents(events=self._events, dialogue=self._dialogue, retaliation=self._retaliation)
        self._executor = PlanExecutor(deps.game_state, agents, cast, self._register_new_npc)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def act(self, input_data: str, context: dict | None = None) -> str:
        """Process a player action and return the narrated response."""
        self._ctx.sync_context(self)

        routing_plan = await self._router.route_action(input_data)

        if routing_plan.get("needs_clarification"):
            self._router.save_pending_clarification(input_data, routing_plan)
            return routing_plan.get(
                "clarification_question",
                "Could you be more specific about what you want to do?",
            )

        self._deps.game_state.pending_clarification = None
        action_type = routing_plan.get(_KEY_ACTION_TYPE, _DEFAULT_ACTION)
        completed = self._events.advance_and_resolve(action_type, routing_plan.get("time_cost_override"))
        narrated = await self._executor.execute_plan(routing_plan, input_data, completed)

        self._ctx.append_turn_logs(input_data, narrated, action_type)
        return narrated

    def register_actor(self, npc_uuid: str, actor: Any) -> None:
        """Register an Actor agent for an NPC."""
        self._actors[npc_uuid] = actor

    def schedule_event(self, event: GameEvent) -> str:
        """Convenience wrapper to schedule an event."""
        return self._deps.event_manager.schedule(event)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _register_new_npc(self, npc: Any) -> None:
        """Register a new NPC in the game state and create an Actor."""
        from cast.actor import Actor
        from knowledge.query import KnowledgeQueryEngine

        self._deps.game_state.npcs[npc.uuid] = npc

        locations = self._deps.game_state.locations
        if npc.location_id and npc.location_id in locations:
            locations[npc.location_id].add_npc(npc.uuid)

        actor = Actor(
            llm_client=self.llm_client,
            npc=npc,
            knowledge_query=KnowledgeQueryEngine(self._deps.game_state.knowledge_graph),
        )
        actor.set_context(language=self._language)
        self.register_actor(npc.uuid, actor)
