"""Plan execution helpers for Director."""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

from cast import (
    _chronicler_goals as chronicler_goals,
    _npc_tactical_goal as tactical_mod,
    director_events,
    director_hostility,
    director_object_interaction as doi_mod,
    director_retaliation,
    director_witness,
    npc_ticker as npc_ticker_mod,
)
from cast import _reliability_metrics as reliability_metrics
from cast.constants import SCENE_CHANGING_ACTIONS, TURN_COUNTING_ACTIONS
from cast.schemas import (
    chronicler_response as chronicler_schema,
    plan_access,
    turn_outputs,
)
from loguru import logger
from models import game_state as game_state_mod, world_state as world_state_mod
from timeline import event as event_mod, event_manager as event_manager_mod

GameState = game_state_mod.GameState

GameEvent = event_mod.GameEvent
EventManager = event_manager_mod.EventManager

_KEY_PLAYER_ACTION = "player_action"
_KEY_GAME_STATE = "game_state"


_SCENE_DESC_PREVIEW = 200
_WAIT_EVENT_LOOKAHEAD_HOURS = 4.0
# Canonical WAIT duration mirrors ``timeline.time_costs.BASE_ACTION_COSTS``.
# Kept as a local constant so the WAIT ambience refresh can render a
# deterministic ``hours_waited`` without pulling an extra module import
# into this file's WPS201 budget.
_WAIT_HOURS_DEFAULT = 0.1
# Cap on ``PlayerState.player_event_log`` length. Older entries are
# trimmed off the front so the Character sidebar stays bounded.
_PLAYER_EVENT_LOG_CAP = 30


def _scene_log_modules() -> tuple[Any, Any]:
    """Lazily import the scene-log helpers as a single statement.

    ``cast``'s module-level import group is already at the WPS235 name
    cap, so these two siblings cannot join it; importing them together
    here keeps this module within the WPS201 import-statement budget
    instead of two separate local imports.
    """
    from cast import scene_log, scene_swap

    return scene_log, scene_swap


def _snapshot_moods(npcs: dict) -> dict[UUID, str]:
    """Capture current mood of every NPC by UUID."""
    return {uuid: npc.current_mood for uuid, npc in npcs.items()}


def _filter_item_targets(targets: list[str], npcs: dict) -> list[str]:
    """Return targets that are NOT NPC names (i.e. likely items/objects)."""
    npc_names_lower = {npc.name.lower() for npc in npcs.values()}
    return [target for target in targets if target.lower() not in npc_names_lower]


def _filter_known_npc_targets(targets: list[str], game_state: GameState) -> list[str]:
    """Keep only targets that match an NPC already known in the scene or game state."""
    scene = game_state.current_scene
    npcs = game_state.npcs

    known: set[str] = set()
    for npc in npcs.values():
        known.add(npc.name.lower())
        if hasattr(npc, "occupation") and npc.occupation:
            known.add(npc.occupation.lower())
    if scene:
        for snpc in scene.npcs_present:
            known.add(snpc.role.lower())

    return [target for target in targets if target.lower() in known]


def _apply_thread_updates(
    state: world_state_mod.WorldState,
    updates: list[chronicler_schema.WorldThreadUpdate],
    current_scene: int,
) -> None:
    """Apply chronicler thread updates in place.

    Matches by ``thread_uuid``; unknown UUIDs are silently ignored so
    a hallucinating Chronicler cannot corrupt the existing threads.
    When ``update.status`` is ``None`` we still bump
    ``last_advanced_scene`` because the Chronicler chose to touch the
    thread this scene.
    """
    by_uuid = {thread.uuid: thread for thread in state.threads}
    for update in updates:
        thread = by_uuid.get(update.thread_uuid)
        if thread is None:
            continue
        if update.status is not None:
            thread.status = update.status
        thread.last_advanced_scene = current_scene


def _ensure_npc_targets_in_scene(
    plan: Any,
    target_names: list[str],
    game_state: GameState,
    dlg: Any,
) -> None:
    """Filter targets and ensure NPC ones are represented in the scene.

    Only creates new SceneNPCs for unknown targets when the Director
    explicitly requested npc_generator.  Otherwise item names like
    "меч" get mistakenly turned into NPCs.
    """
    npc_targets = (
        target_names
        if "npc_generator" in plan_access.delegate_to(plan)
        else _filter_known_npc_targets(target_names, game_state)
    )
    dlg.ensure_targets_in_scene(npc_targets)


class PlanExecutor:
    """Executes a routing plan by coordinating sub-agents."""

    def __init__(
        self,
        *,
        game_state: GameState,
        events: director_events.EventProcessor,
        event_manager: EventManager,
        dialogue: Any,
        retaliation: director_retaliation.RetaliationHandler,
        npc_turns: Any,
        npc_ticker: npc_ticker_mod.NPCTicker,
        memory_manager: Any,
        scene_builder: Any,
        narrator: Any,
        npc_generator: Any,
        data_miner: Any,
        item_generator: Any,
        world_chronicler: Any | None = None,
        dramaturge: Any | None = None,
        register_npc_fn: Any = None,
    ) -> None:
        self._gs = game_state
        self._events = events
        self._event_manager = event_manager
        self._dialogue = dialogue
        self._retaliation = retaliation
        self._npc_turns = npc_turns
        self._npc_ticker = npc_ticker
        self._memory_manager = memory_manager
        self._scene_builder = scene_builder
        self._narrator = narrator
        self._npc_generator = npc_generator
        self._data_miner = data_miner
        self._item_generator = item_generator
        self._world_chronicler = world_chronicler
        self._dramaturge = dramaturge
        self._register_npc = register_npc_fn

    async def execute_plan(
        self,
        plan: Any,
        player_action: str,
        completed_events: list[GameEvent],
    ) -> str:
        """Delegate to agents based on the routing plan and assemble output."""
        raw_outputs = turn_outputs.TurnOutputs(intent=plan.intent)
        action_type = plan.action_type
        is_aggressive = plan_access.is_aggressive(plan)

        # Record the player's action at the head of this turn's log, before
        # NPC reactions are appended (so next turn's NPCs read it ahead of
        # their own replies) and before _prepare_scene consolidates/clears
        # the outgoing scene (so a MOVE/SLEEP trigger lands in the scene it
        # ends, not the one it opens). Indexed (not unpacked) to keep
        # execute_plan within its WPS210 local-variable budget.
        _scene_log_modules()[0].append_player_action(self._gs, action_type, player_action, is_aggressive=is_aggressive)

        local_events = await self._process_events(completed_events)
        new_uuids = await self._dispatch_plan(plan, action_type, player_action, raw_outputs)

        if local_events:
            raw_outputs.completed_events = [ev.on_complete_description or ev.name for ev in local_events]

        await self._resolve_npc_turns(action_type, player_action, raw_outputs, is_aggressive)
        self._npc_ticker.tick(raw_outputs, skip_uuids=new_uuids)
        # Tactical TTL sweep follows the NPC ticker so any NPC the ticker
        # just evicted is no longer in scene when expiry conditions are
        # checked. Stale tactical goals would otherwise wedge a vengeful
        # NPC's intent against a target who walked away three turns ago.
        tactical_mod.tick_tactical_ttl(self._gs)

        if raw_outputs.scene is not None:
            await self._handle_scene_change(raw_outputs, player_action, completed_events)
        elif raw_outputs.wait:
            await self._refresh_scene_ambience(raw_outputs, player_action, completed_events)

        self._append_player_event_log(raw_outputs)
        return await self._narrate_and_review(raw_outputs, player_action)

    def _append_player_event_log(self, raw_outputs: turn_outputs.TurnOutputs) -> None:
        """Append this turn's narrator-consumed highlights to the player event log.

        Reuses the same strings the Narrator reads from ``raw_outputs``
        — newly introduced NPC labels, completed local events, and
        object-interaction narrations — so the Character sidebar mirrors
        the prose without a separate summarisation pass. The log is
        capped at :data:`_PLAYER_EVENT_LOG_CAP` entries, with the oldest
        trimmed off the front.
        """
        player = self._gs.player
        player.player_event_log.extend(raw_outputs.new_npcs)
        player.player_event_log.extend(raw_outputs.completed_events)
        player.player_event_log.extend(raw_outputs.object_interactions)
        if len(player.player_event_log) > _PLAYER_EVENT_LOG_CAP:
            player.player_event_log = player.player_event_log[-_PLAYER_EVENT_LOG_CAP:]

    async def _dispatch_plan(
        self,
        plan: Any,
        action_type: str,
        player_action: str,
        raw_outputs: turn_outputs.TurnOutputs,
    ) -> set[UUID]:
        """Run the scene-prep + action-specific handlers for the turn.

        Splits the per-action-type branching out of :meth:`execute_plan`
        so the outer coordinator stays within the cognitive-complexity
        budget. Returns the union of UUIDs for NPCs newly generated by
        either scene prep or target processing, so the caller can pass
        them into the NPC ticker as ``skip_uuids``.
        """
        if action_type == "WAIT":
            raw_outputs.wait = True
            wait_reason = getattr(plan, "wait_reason", None)
            if wait_reason:
                raw_outputs.wait_reason = wait_reason
            return set()
        targets = plan_access.targets(plan)
        is_aggressive = plan_access.is_aggressive(plan)
        new_uuids = await self._prepare_scene(action_type, targets, player_action, raw_outputs)
        new_uuids |= await self._process_target_npcs(plan, player_action, raw_outputs)
        await self._run_action_handler(action_type, targets, player_action, is_aggressive, raw_outputs)
        return new_uuids

    async def _run_action_handler(
        self,
        action_type: str,
        targets: list[str],
        player_action: str,
        is_aggressive: bool,
        raw_outputs: turn_outputs.TurnOutputs,
    ) -> None:
        """Dispatch EXAMINE / INTERACT to the matching object handler.

        Both branches are best-effort: silently skip when the action
        is not one of these or when the target list is empty. The
        ``is_aggressive`` flag only affects the INTERACT branch — it
        feeds the KER-18 proximity-witness broadcast so guards react
        when the player smashes an inanimate target.
        """
        if action_type == "EXAMINE":
            item_desc = await self._examine_items(targets, player_action)
            if item_desc:
                raw_outputs.item_examination = item_desc
        elif action_type == "INTERACT":
            await self._interact_with_objects(targets, player_action, is_aggressive, raw_outputs)

    async def _handle_scene_change(
        self,
        raw_outputs: turn_outputs.TurnOutputs,
        player_action: str,
        completed_events: list[GameEvent],
    ) -> None:
        """Run the scene-change side effects: rumour propagation + world chronicler.

        Both side effects share a single scene-change boundary check
        with the narration path inside ``execute_plan``.
        """
        self._events.propagate_rumors_for_turn(completed_events)
        if self._world_chronicler is not None:
            await self._advance_world_state(raw_outputs, player_action)

    async def _narrate_and_review(
        self,
        raw_outputs: turn_outputs.TurnOutputs,
        player_action: str,
    ) -> str:
        """Narrate the turn and optionally run the Dramaturge consistency pass.

        The Dramaturge only runs on new-scene turns (the KER-5
        "sync-on-new-scene" gate that bounds per-turn latency) and
        only when one is wired on the cast. Continuation turns pass
        the Narrator output through unchanged.

        On any unexpected exception from the review, we log and
        return the raw Narrator output — the player must never see a
        half-rewritten passage. The Dramaturge has its own internal
        fallback, so this wrap is belt-and-braces against future
        changes that might let an exception escape ``act()``.
        """
        narration = await self._narrator.execute(
            input_data=raw_outputs,
            context={
                _KEY_PLAYER_ACTION: player_action,
                _KEY_GAME_STATE: self._gs,
                "scene_history": self._gs.scene_conversation_log[-5:],
            },
        )
        if self._dramaturge is None or raw_outputs.scene is None:
            return narration
        try:
            return await self._dramaturge.execute(
                input_data=narration,
                context={
                    _KEY_PLAYER_ACTION: player_action,
                    _KEY_GAME_STATE: self._gs,
                    "data_miner": self._data_miner,
                },
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Dramaturge execute() raised unexpectedly; returning raw Narrator output")
            reliability_metrics.record_fallback("director", "dramaturge_execute")
            return narration

    async def _advance_world_state(
        self,
        raw_outputs: turn_outputs.TurnOutputs,
        player_action: str,
    ) -> None:
        """Ask the World Chronicler to update world threads and mood.

        Only called when a new scene was built this turn and a
        ``world_chronicler`` is wired on the cast. Applies the response
        in place on ``game_state.world_state`` and schedules any
        chronicler-produced offscreen events through
        :meth:`EventProcessor.schedule_drafts` so the timeline boundary
        stays inside :mod:`cast.director_events`.
        """
        assert self._world_chronicler is not None
        response: chronicler_schema.ChroniclerResponse = await self._world_chronicler.execute(
            input_data=raw_outputs,
            context={_KEY_PLAYER_ACTION: player_action, _KEY_GAME_STATE: self._gs},
        )
        state = self._gs.world_state
        scene_number = self._gs.scene_number
        for draft in response.new_threads:
            state.threads.append(
                world_state_mod.WorldThread(
                    description=draft.description,
                    category=draft.category,
                    introduced_scene=scene_number,
                    involved_locations=[
                        location_id for location_id in draft.involved_locations if location_id in self._gs.locations
                    ],
                    involved_npcs=[npc_uuid for npc_uuid in draft.involved_npcs if npc_uuid in self._gs.npcs],
                    last_advanced_scene=scene_number,
                ),
            )
        _apply_thread_updates(state, response.thread_updates, scene_number)
        # Apply Chronicler-emitted life-goal drafts/updates after threads
        # so a draft's ``source_thread_uuid`` references a thread that
        # already exists on ``state``.
        chronicler_goals.apply_goal_drafts(self._gs.npcs, response.goal_drafts)
        chronicler_goals.apply_goal_updates(self._gs.npcs, response.goal_updates)
        if response.world_mood is not None:
            state.world_mood = response.world_mood
        state.last_chronicled_scene = scene_number

        if response.scheduled_events:
            self._events.schedule_drafts(
                response.scheduled_events,
                now=self._gs.game_clock,
            )

    async def _refresh_scene_ambience(
        self,
        raw_outputs: turn_outputs.TurnOutputs,
        player_action: str,
        completed_events: list[GameEvent],
    ) -> None:
        """Populate ``raw_outputs.wait_context`` with living-world motion on WAIT turns.

        1. Re-invokes the World Chronicler via :meth:`_advance_world_state`
           (no-op when ``world_chronicler`` is not wired) so ``world_state.threads``
           advance and ``world_mood`` refreshes.
        2. Collects open :class:`WorldThread` s whose ``involved_locations``
           include ``game_state.player.location_id``.
        3. Filters ``location.npcs_present`` UUIDs for NPCs currently on-shift
           per the :class:`NPCTicker` schedule tables.
        4. Collects completed-this-turn and soon-firing local
           :class:`GameEvent` s from the :class:`EventManager`.
        5. Packages everything into a :class:`WaitContext` attached to
           ``raw_outputs``.

        Called from :meth:`execute_plan` after ``_resolve_npc_turns`` and
        ``npc_ticker.tick`` so the ambient picture already includes any
        departures. ``advance_and_resolve`` has already run in
        :meth:`Director.act` before this code path, so ``completed_events``
        is populated for the imminent-events collector.
        """
        if self._world_chronicler is not None:
            await self._advance_world_state(raw_outputs, player_action)

        location_id = self._gs.player.location_id
        raw_outputs.wait_context = turn_outputs.WaitContext(
            active_threads=self._collect_active_threads(location_id),
            on_shift_npcs=self._collect_on_shift_npcs(location_id),
            imminent_events=self._collect_imminent_events(location_id, completed_events),
            hours_waited=_WAIT_HOURS_DEFAULT,
        )

    def _collect_active_threads(self, location_id: UUID | None) -> list[world_state_mod.WorldThread]:
        """Return open world threads whose ``involved_locations`` touch ``location_id``."""
        return [
            thread
            for thread in self._gs.world_state.threads
            if thread.status == "open" and location_id in thread.involved_locations
        ]

    def _collect_on_shift_npcs(self, location_id: UUID | None) -> list[str]:
        """Return 'Name (Occupation)' labels for NPCs currently on-shift at ``location_id``.

        Returns an empty list when the location is unknown or the
        player has no location fix yet — the WAIT turn should still
        work in that degraded case. The per-NPC shift check is
        extracted into :meth:`_on_shift_label` to keep both methods
        under the project-wide cognitive-complexity budget.
        """
        if location_id is None or location_id not in self._gs.locations:
            return []
        labels: list[str] = []
        for npc_uuid in self._gs.locations[location_id].npcs_present:
            label = self._on_shift_label(npc_uuid)
            if label is not None:
                labels.append(label)
        return labels

    def _on_shift_label(self, npc_uuid: UUID) -> str | None:
        """Return the display label for an on-shift NPC, or ``None`` otherwise.

        Reuses :func:`cast.npc_ticker.get_schedule_for` so the
        "is this NPC present right now?" rule stays in one place.
        Returns ``None`` for unknown UUIDs and for NPCs whose schedule
        slot is explicitly ``present=False`` at the current
        ``game_state.game_time``.
        """
        npc = self._gs.npcs.get(npc_uuid)
        if npc is None:
            return None
        slot = npc_ticker_mod.get_schedule_for(npc.occupation).get(self._gs.game_time)
        if slot is not None and not slot.present:
            return None
        return npc.label_for_player(self._gs, npc.occupation or "resident")

    def _collect_imminent_events(
        self,
        location_id: UUID | None,
        completed_events: list[GameEvent],
    ) -> list[str]:
        """Return human-readable lines for just-completed and soon-firing local events.

        Combines the events that completed during this turn's clock
        advance (from :meth:`Director.act`'s ``advance_and_resolve`` call)
        with pending events at the player's location whose
        ``completes_at`` falls within ``_WAIT_EVENT_LOOKAHEAD_HOURS`` of
        the current game clock.
        """
        lines = [ev.on_complete_description or ev.name for ev in completed_events]
        lookahead = self._gs.game_clock + _WAIT_EVENT_LOOKAHEAD_HOURS
        for pending in self._event_manager.get_pending_events():
            if pending.location_id == location_id and pending.completes_at <= lookahead:
                lines.append(pending.on_complete_description or pending.name)
        return lines

    async def _resolve_npc_turns(
        self,
        action_type: str,
        player_action: str,
        raw_outputs: turn_outputs.TurnOutputs,
        is_aggressive: bool = False,
    ) -> None:
        """Resolve NPC autonomous turns for turn-counting or aggressive actions.

        Passes ``raw_outputs.witnessed_events`` through to the resolver
        so guard NPCs see the KER-18 incident clause on the same turn
        the vandalism is committed — the witness broadcast step ran
        earlier inside :meth:`_interact_with_objects`.

        ``is_aggressive`` (KER-21) is forwarded so the resolver can
        serialize NPC reactions when the player attacks, letting each
        successive NPC see what its peers just did and diversifying
        the combat response away from a single template. An aggressive
        turn also bypasses the ``TURN_COUNTING_ACTIONS`` gate (KER-33):
        the router sometimes classifies a punch as ``OTHER`` while
        still flagging it aggressive, and bystanders must react to
        visible violence regardless of the action-type label.
        """
        if action_type not in TURN_COUNTING_ACTIONS and not is_aggressive:
            return
        npc_actions = await self._npc_turns.resolve_npc_turns(
            player_action,
            witnessed_events=raw_outputs.witnessed_events,
            is_aggressive=is_aggressive,
            player_action_type=action_type,
        )
        await self._npc_turns.apply_goal_aftermath(npc_actions, self._memory_manager)
        if npc_actions:
            raw_outputs.npc_turns = [
                turn_outputs.NPCTurnEntry(
                    npc_uuid=npc_act.npc_uuid,
                    npc_name=npc_act.npc_name,
                    action=npc_act.action_description,
                    action_type=npc_act.action_type,
                )
                for npc_act in npc_actions
            ]

    async def _process_events(self, completed_events: list[GameEvent]) -> list[GameEvent]:
        """Partition events, process remote ones, return local events."""
        local, remote = self._events.partition_events(completed_events)
        if remote:
            await self._events.process_remote_events(remote)
        return local

    async def _process_target_npcs(
        self,
        plan: Any,
        player_action: str,
        raw_outputs: turn_outputs.TurnOutputs,
    ) -> set[UUID]:
        """Ensure targeted NPCs exist in the scene, run interactions.

        Returns the UUIDs of any NPCs freshly generated by
        ``init_scene_npcs`` during this call. :meth:`execute_plan`
        hands those UUIDs to :class:`NPCTicker` as ``skip_uuids`` so
        the ticker never evicts an NPC that did not exist before this
        very turn.
        """
        dlg = self._dialogue
        target_names = plan_access.targets(plan)
        new_uuids: set[UUID] = set()
        if target_names:
            _ensure_npc_targets_in_scene(plan, target_names, self._gs, dlg)
            new_npcs = await dlg.init_scene_npcs(
                self._npc_generator,
                self._register_npc,
                self._item_generator,
            )
            if new_npcs:
                raw_outputs.new_npcs = [npc.label_for_player(self._gs, npc.occupation) for npc in new_npcs]
                new_uuids = {npc.uuid for npc in new_npcs}

        should_talk = dlg.targets_match_scene_npcs(target_names) or "actor" in plan_access.delegate_to(plan)
        if should_talk or plan.action_type == "TALK":
            await self._run_interactions(
                player_action,
                target_names,
                plan_access.is_aggressive(plan),
                raw_outputs,
                plan_access.contest_as_dict(plan),
            )
        return new_uuids

    async def _prepare_scene(
        self,
        action_type: str,
        targets: list[str],
        player_action: str,
        raw_outputs: turn_outputs.TurnOutputs,
    ) -> set[UUID]:
        """Build scene if needed and initialise any uninitialised NPCs.

        Rebuild fires when the action moves the player (MOVE) or
        advances the clock past a narrative beat (SLEEP), or when
        there is no current scene yet. EXPLORE / LOOK in the same
        location+time-of-day reuses the existing scene so pre-seeded
        or previously-generated NPCs are not orphaned (KER-33).

        Returns the UUIDs of any NPCs freshly generated by
        ``init_scene_npcs`` during this call. They are subsequently
        passed to :class:`NPCTicker` as ``skip_uuids`` so that a
        bartender placed by the Scene Builder in a morning tavern is
        not evicted the same turn the player first arrives.
        """
        needs_rebuild = self._gs.current_scene is None or action_type in SCENE_CHANGING_ACTIONS
        # Skip rebuild when MOVE targets are all NPCs already in the scene
        # (e.g. "walk to the guard" — no location change).
        if needs_rebuild and action_type == "MOVE" and targets:
            known = _filter_known_npc_targets(targets, self._gs)
            if len(known) == len(targets):
                needs_rebuild = False
        if needs_rebuild:
            scene = await self._scene_builder.execute(
                input_data=player_action,
                context={_KEY_GAME_STATE: self._gs},
            )
            raw_outputs.scene = scene
            outgoing = self._gs.current_scene
            if outgoing is not None:
                # Consolidate-then-clear is atomic: only wipe the log once
                # its entries (including this turn's just-appended player
                # trigger) have been handed to the consolidator. On the
                # first turn there is no outgoing scene, so the player's
                # opening action must survive into the new scene's log.
                await self._consolidate_outgoing_scene(outgoing)
                self._gs.scene_action_log = []
            self._gs.current_scene = scene
            self._gs.scene_number += 1
            self._gs.scene_conversation_log = []

        new_npcs = await self._dialogue.init_scene_npcs(
            self._npc_generator,
            self._register_npc,
            self._item_generator,
        )
        # Once every present NPC has a stable UUID, mirror any life-tier
        # KILL/PURSUE into the tactical slot for on-sight engagement so
        # the same-turn Actor pass sees an immediate intent. No-op when
        # no co-located target exists.
        tactical_mod.promote_life_goals_on_sight(self._gs)
        return {npc.uuid for npc in new_npcs}

    async def _consolidate_outgoing_scene(self, outgoing_scene: Any) -> None:
        """Persist the outgoing scene's action log as long-term memory.

        Best-effort: scene memory is enrichment, not turn-critical. A
        consolidation failure (LLM timeout, rate limit) must not abort
        the turn — the caller still clears the log and completes the
        scene swap. Leaving the log un-cleared on failure would
        re-consolidate (and double-write) it on the next swap, so the
        clear deliberately runs regardless of this method's outcome.
        """
        try:
            await _scene_log_modules()[1].consolidate_outgoing_scene(self._memory_manager, self._gs, outgoing_scene)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "Scene consolidation failed (location={}, log_entries={}); skipping enrichment for this scene",
                getattr(outgoing_scene, "location_id", None),
                len(self._gs.scene_action_log),
            )
            reliability_metrics.record_fallback("director", "scene_consolidation")

    async def _examine_items(self, targets: list[str], player_action: str) -> list[str]:
        """Examine items from scene or NPC inventories via the ItemGenerator."""
        item_targets = _filter_item_targets(targets, self._gs.npcs)
        if not item_targets or not self._item_generator:
            return []

        scene = self._gs.current_scene
        hint = scene.description[:_SCENE_DESC_PREVIEW] if scene else "unknown location"

        return list(
            await asyncio.gather(
                *(
                    self._item_generator.execute(
                        input_data=name,
                        context={"mode": "examine", _KEY_GAME_STATE: self._gs, "context_hint": hint},
                    )
                    for name in item_targets
                )
            )
        )

    async def _interact_with_objects(
        self,
        targets: list[str],
        player_action: str,
        is_aggressive: bool,
        raw_outputs: turn_outputs.TurnOutputs,
    ) -> None:
        """Resolve INTERACT actions whose targets are pure scene objects.

        Only non-NPC targets are forwarded — NPC targets are already
        handled by the dialogue / retaliation pipeline in
        :meth:`_process_target_npcs`. The filter combines name-level
        matching against ``game_state.npcs`` with role-level matching
        against the current ``Scene.npcs_present`` so "punch the guard"
        does not fall through into the object-interaction handler when
        dialogue has already processed the guard.

        Narrations collected from
        :func:`cast.director_object_interaction.apply_object_interactions`
        are hung off the turn outputs so the Narrator can inline them
        with the scene description. When ``is_aggressive`` is true the
        KER-18 proximity-witness broadcast fires so guard NPCs standing
        in the scene get both a ``WitnessedAggression`` record on
        ``raw_outputs`` and a ``threatened`` mood flip.
        """
        object_targets = self._pure_object_targets(targets)
        if not object_targets:
            return
        interaction = await doi_mod.apply_object_interactions(
            self._item_generator,
            object_targets,
            player_action,
            self._gs,
            self._memory_manager,
        )
        if interaction.narrations:
            raw_outputs.object_interactions = interaction.narrations
        if is_aggressive and any(interaction.deltas):
            self._publish_object_witness(object_targets, interaction.deltas, player_action, raw_outputs)

    def _publish_object_witness(
        self,
        object_targets: list[str],
        deltas: list[str],
        player_action: str,
        raw_outputs: turn_outputs.TurnOutputs,
    ) -> None:
        """Broadcast a :class:`WitnessedAggression` + bump guard moods (KER-18).

        Builds one witness record per non-empty ``(target, delta)``
        pair and appends it to ``raw_outputs.witnessed_events``. Then
        flips neutral-mood guard witnesses to ``"threatened"`` so the
        existing retaliation pipeline wakes up on subsequent aggressive
        turns, and the same-turn NPC autonomous prompt sees the
        elevated mood plus an incident clause in
        :func:`cast.npc_turn._build_turn_prompt`.
        """
        scene = self._gs.current_scene
        if scene is None:
            return
        for target, delta in zip(object_targets, deltas):
            if not delta:
                continue
            raw_outputs.witnessed_events.append(
                director_witness.build_object_smash_witness(
                    target=target,
                    delta_text=delta,
                    player_action=player_action,
                    location_id=scene.location_id,
                ),
            )
        if not raw_outputs.witnessed_events:
            return
        guard_uuids = self._guard_witness_uuids()
        director_witness.bump_guard_moods(self._gs, guard_uuids)

    def _guard_witness_uuids(self) -> list[UUID]:
        """Return UUIDs of guard-occupation witnesses in the current scene."""
        return [
            uuid
            for uuid in doi_mod.initialised_scene_witnesses(self._gs)
            if director_witness.is_guard_occupation(self._gs.npcs[uuid].occupation)
        ]

    def _publish_npc_attack_witness(
        self,
        target_names: list[str],
        player_action: str,
        raw_outputs: turn_outputs.TurnOutputs,
    ) -> None:
        """Broadcast a :class:`WitnessedAggression` + bump guard moods for NPC-target aggression (KER-33).

        Mirrors :meth:`_publish_object_witness`: the KER-18 mood-flip
        originally fired only when the player smashed an object, which
        left bystander guards standing frozen when the player punched
        a person instead. Every guard-occupation NPC in the scene gets
        the bump — the attacked target has already been pushed past
        ``"neutral"`` by ``apply_aggressive_turn``, so
        :func:`bump_guard_moods`'s neutral-only gate naturally skips
        them. Elevated mood is threaded into the NPC-turn prompt on
        the same turn via ``raw_outputs.witnessed_events``.
        """
        scene = self._gs.current_scene
        if scene is None:
            return
        for target_name in target_names:
            raw_outputs.witnessed_events.append(
                director_witness.build_npc_attack_witness(
                    target_name=target_name,
                    player_action=player_action,
                    location_id=scene.location_id,
                ),
            )
        director_witness.bump_guard_moods(self._gs, self._guard_witness_uuids())

    def _pure_object_targets(self, targets: list[str]) -> list[str]:
        """Return targets that match neither an NPC name nor a scene role.

        Uses the same role/name filter as :func:`_filter_known_npc_targets`
        and subtracts its result from the full target list so targets
        like ``"guard"`` — which matches a SceneNPC role even without a
        registered ``NPCCard`` — are never forwarded to the
        object-interaction handler.
        """
        npc_matches = {target.lower() for target in _filter_known_npc_targets(targets, self._gs)}
        return [target for target in targets if target.lower() not in npc_matches]

    async def _run_interactions(
        self,
        player_action: str,
        target_names: list[str],
        is_aggressive: bool,
        raw_outputs: turn_outputs.TurnOutputs,
        contest_info: dict | None = None,
    ) -> None:
        """Run NPC dialogue and retaliation checks.

        On aggressive turns the Director bumps ``hostility_level`` on each
        targeted NPC *before* dialogue runs, replacing the LLM's fragile
        ``[MOOD:]`` ratchet with a deterministic counter.

        When a dialogue call already carries a combat contest roll (player
        attacks NPC directly), the Actor physically retaliates inside that
        response. For NPCs whose hostility has not yet crossed the
        retaliation threshold we pass those UUIDs to ``check_retaliation`` as
        ``skip_uuids`` so the phase does not fire a second, redundant Actor
        call. NPCs at or above the threshold are *forced* to roll
        aggression even if the combat dice already landed, so repeat
        assaults get an offensive counter-attack.
        """
        mood_snapshot = _snapshot_moods(self._gs.npcs)
        force_uuids = (
            director_hostility.apply_aggressive_turn(self._gs, target_names, player_action) if is_aggressive else set()
        )
        if is_aggressive and target_names:
            self._publish_npc_attack_witness(target_names, player_action, raw_outputs)
            # Stamp a tactical DEFEND on every NPC that crossed the
            # retaliation threshold so the immediate next-turn Actor pass
            # has a concrete short-term intent to drive on, separate from
            # any longer-lived life_goal the NPC may already carry.
            tactical_mod.assign_defend_goals_from_aggression(self._gs, force_uuids, player_action)

        dialogue_entries, combat_engaged = await self._dialogue.handle_dialogue(
            player_action,
            target_names,
            is_aggressive=is_aggressive,
            contest_info=contest_info,
        )
        if dialogue_entries:
            raw_outputs.dialogue = [turn_outputs.DialogueEntry(**entry) for entry in dialogue_entries]

        retaliation_entries = await self._retaliation.check_retaliation(
            mood_snapshot,
            skip_uuids=combat_engaged - force_uuids,
            force_uuids=force_uuids,
        )
        if retaliation_entries:
            await self._dialogue.summarize_retaliations(retaliation_entries, player_action)
            raw_outputs.dialogue.extend(turn_outputs.DialogueEntry(**entry) for entry in retaliation_entries)
