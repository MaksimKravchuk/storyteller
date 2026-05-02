"""Object-interaction routing for INTERACT-with-object turns (KER-13).

Before this module existed, ``INTERACT`` player actions whose targets
were pure objects (no NPC match) fell through every dispatch branch
in :class:`cast.director_execution.PlanExecutor` — the turn advanced
the clock but left no narration, no persistent state, and no witness
memories. This meant "break the window" silently evaporated and the
next visit to the same scene regenerated a pristine description.

``apply_object_interactions`` now gives those turns a real handler:

1. Dispatches each object target to the :class:`ItemGenerator` in
   ``"interact"`` mode. The LLM returns a short physical narration
   plus a persistent ``delta`` string.
2. Persists each non-empty delta as a ``scene_state``-tagged node in
   the knowledge graph via :func:`knowledge.scene_state.record_scene_delta`,
   so the Scene Builder can re-read it on any future rebuild of the
   same ``location_id``.
3. Emits a ``PERSONAL_EXPERIENCE`` witness memory for every
   initialised scene NPC via
   :meth:`MemoryManager.create_memory_from_event` so NPCs who were
   standing there can recall the event on subsequent turns.

The witness-set rule mirrors KER-11 (scene co-witnesses for dialogue):
"all initialised NPCs in the current scene". Unlike the KER-11 helper
there is no excluded-targets set — an object has no ``NPCCard``.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any
from uuid import UUID

from loguru import logger

from cast.schemas.item_response import ObjectInteractionResponse, ObjectInteractionResult
from knowledge.memory import record_player_learned_fact
from knowledge.node import KnowledgeScope
from knowledge.scene_state import record_scene_delta
from llm.turn_event_logger import record_turn_event

if TYPE_CHECKING:
    from knowledge.memory import MemoryManager
    from models.game_state import GameState

_SCENE_DESC_PREVIEW = 200


def _scene_hint(game_state: GameState) -> str:
    """Return the short scene-description preview fed into the LLM prompt."""
    scene = game_state.current_scene
    if scene is None:
        return "unknown location"
    return scene.description[:_SCENE_DESC_PREVIEW]


def initialised_scene_witnesses(game_state: GameState) -> list[UUID]:
    """Return UUIDs of every initialised NPC in the current scene.

    Uninitialised ``SceneNPC`` stubs are skipped for the same reason as
    KER-11: they have no graph node yet, so a ``WITNESSED`` edge would
    dangle. A scene NPC counts as initialised when its ``uuid`` is set
    *and* the matching ``NPCCard`` is already registered.

    Exported (no leading underscore) so the KER-18 witness-broadcast
    path in :mod:`cast.director_execution` can reuse the same filter
    instead of duplicating the six-line scan.
    """
    scene = game_state.current_scene
    if scene is None:
        return []
    registered = game_state.npcs
    candidates = (snpc.uuid for snpc in scene.npcs_present)
    return [uid for uid in candidates if uid is not None and uid in registered]


async def _run_single_interaction(
    item_generator: Any,
    object_name: str,
    player_action: str,
    game_state: GameState,
) -> ObjectInteractionResponse:
    """Dispatch one object target to the ItemGenerator in interact mode."""
    return await item_generator.execute(
        input_data=object_name,
        context={
            "mode": "interact",
            "game_state": game_state,
            "player_action": player_action,
            "context_hint": _scene_hint(game_state),
        },
    )


def _persist_delta(
    game_state: GameState,
    object_key: str,
    delta_text: str,
) -> None:
    """Persist a non-empty delta for ``object_key`` at the current location.

    Writes both sinks (``scene_state`` knowledge node and the typed
    ``Location.object_states`` channel) or neither — the shared
    early-return guard on ``delta_text``, ``scene``, and ``object_key``
    keeps the two sources of truth aligned so a bystander reading
    persistent world changes never sees a delta the Narrator's
    ``Prior damage:`` line omits.
    """
    scene = game_state.current_scene
    if not delta_text or not object_key or scene is None:
        return
    record_scene_delta(
        game_state.knowledge_graph,
        location_id=scene.location_id,
        delta_text=delta_text,
        game_time=game_state.game_clock,
    )
    location = game_state.locations.get(scene.location_id)
    if location is None:
        logger.warning(
            "_persist_delta: scene.location_id={0} not in game_state.locations; typed channel skipped",
            scene.location_id,
        )
        return
    location.record_object_state(object_key, delta_text)


def _persist_and_record(
    game_state: GameState,
    object_targets: list[str],
    player_action: str,
    responses: list[ObjectInteractionResponse],
) -> None:
    """Write deltas to both persistence sinks *and* emit one turn event per target.

    Extracted into its own function so the loop variable does not
    leak into the enclosing scope — the enclosing coroutine later
    issues an ``asyncio.gather`` over a comprehension with its own
    ``delta`` name, which tripped WPS441 when both lived in the same
    function body.
    """
    for object_key, resp in zip(object_targets, responses):
        _persist_delta(game_state, object_key, resp.delta)
        record_turn_event(
            "object_interaction",
            {
                "object_name": object_key,
                "player_action": player_action,
                "narration": resp.narration,
                "delta": resp.delta,
            },
        )


async def _emit_witness_memories(
    memory_manager: MemoryManager,
    game_state: GameState,
    delta_text: str,
) -> None:
    """Broadcast a ``PERSONAL_EXPERIENCE`` memory to initialised scene NPCs.

    Short-circuits when there is nothing to remember (no witnesses or
    empty delta) so a silent "bumping into a wall" INTERACT does not
    spam the graph with ghost memory nodes.
    """
    witnesses = initialised_scene_witnesses(game_state)
    if not witnesses or not delta_text:
        return
    scene = game_state.current_scene
    created_ids = await memory_manager.create_memory_from_event(
        event_description=delta_text,
        witness_ids=witnesses,
        scope=KnowledgeScope.LOCAL,
        location_id=scene.location_id if scene else None,
        game_time=game_state.game_clock,
    )
    record_player_learned_fact(game_state.player, created_ids)


async def apply_object_interactions(
    item_generator: Any,
    object_targets: list[str],
    player_action: str,
    game_state: GameState,
    memory_manager: MemoryManager,
) -> ObjectInteractionResult:
    """Resolve every object target in the INTERACT plan.

    Runs the ``ItemGenerator`` interact mode concurrently for each
    target, writes every non-empty delta to the knowledge graph, and
    broadcasts a witness memory to all initialised scene NPCs. Returns
    a :class:`ObjectInteractionResult` bundling the narration strings
    (for ``TurnOutputs.object_interactions``) and the parallel delta
    list (for the KER-18 witness-broadcast path in
    :class:`cast.director_execution.PlanExecutor`).

    Silently skips when there is no ``ItemGenerator`` wired or when
    the target list is empty.
    """
    if not object_targets or item_generator is None:
        return ObjectInteractionResult(narrations=[], deltas=[])
    responses: list[ObjectInteractionResponse] = list(
        await asyncio.gather(
            *(_run_single_interaction(item_generator, target, player_action, game_state) for target in object_targets),
        ),
    )
    deltas = [resp.delta for resp in responses]
    _persist_and_record(game_state, object_targets, player_action, responses)
    await asyncio.gather(
        *(_emit_witness_memories(memory_manager, game_state, delta) for delta in deltas),
    )
    narrations = [resp.narration for resp in responses if resp.narration]
    return ObjectInteractionResult(narrations=narrations, deltas=deltas)
