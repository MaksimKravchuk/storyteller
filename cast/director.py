"""Director — central orchestrator of the text quest engine."""

from __future__ import annotations

import dataclasses
from typing import Any

from cast.base_performer_class import BasePerformer
from cast import director_context, director_dialogue, director_events
from cast import director_execution, director_retaliation, director_routing
from cast.npc_turn import NPCTurnResolver
from cast.wait_detection import build_forced_wait_plan, detect_wait_intent, is_incapacitated
from knowledge import memory as memory_mod
from models import game_state as gs_mod
from prompts import director_prompts
from timeline import event as event_mod, event_manager as event_manager_mod

_KEY_ACTION_TYPE = "action_type"
_DEFAULT_ACTION = "OTHER"


@dataclasses.dataclass
class DirectorDeps:
    """Runtime dependencies the Director needs to orchestrate the game."""

    game_state: gs_mod.GameState
    event_manager: event_manager_mod.EventManager
    memory_manager: memory_mod.MemoryManager


@dataclasses.dataclass
class DirectorCast:
    """The ensemble of specialist agents the Director delegates to."""

    scene_builder: Any
    narrator: Any
    npc_generator: Any
    data_miner: Any
    item_generator: Any
    actors: dict[str, Any] = dataclasses.field(default_factory=dict)


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
            system_prompt_template=director_prompts.DIRECTOR_SYSTEM,
        )
        self._deps = deps
        self._cast = cast
        self._actors: dict[str, Any] = dict(cast.actors)
        self._language = language

        self._ctx = director_context.ContextFormatter(deps.game_state)
        self._router = director_routing.ActionRouter(deps.game_state, self._send_json)
        self._events = director_events.EventProcessor(deps.game_state, deps.event_manager, deps.memory_manager)
        self._dialogue = director_dialogue.DialogueHandler(deps.game_state, self._actors)
        self._retaliation = director_retaliation.RetaliationHandler(deps.game_state, self._actors)
        self._npc_turns = NPCTurnResolver(deps.game_state, self._actors)
        agents = director_execution._Agents(
            events=self._events,
            dialogue=self._dialogue,
            retaliation=self._retaliation,
            npc_turns=self._npc_turns,
        )
        self._executor = director_execution.PlanExecutor(deps.game_state, agents, cast, self._register_new_npc)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def act(self, input_data: str, context: dict | None = None) -> str:
        """Process a player action and return the narrated response."""
        self._ctx.sync_context(self)

        routing_plan = self._check_forced_wait(input_data)
        if routing_plan is None:
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

    def schedule_event(self, event: event_mod.GameEvent) -> str:
        """Convenience wrapper to schedule an event."""
        return self._deps.event_manager.schedule(event)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _check_forced_wait(self, input_data: str) -> dict | None:
        """Short-circuit to WAIT if player is incapacitated or typed a wait keyword."""
        player_status = self._deps.game_state.player.physical_status
        if is_incapacitated(player_status):
            return build_forced_wait_plan(player_status)
        if detect_wait_intent(input_data, self._language):
            return build_forced_wait_plan("voluntary")
        return None

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
