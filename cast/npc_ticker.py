"""Deterministic schedule-driven NPC movement between turns.

The :class:`NPCTicker` is the non-LLM counterpart to
:class:`cast.npc_turn.NPCTurnResolver`. It runs once per turn after
the LLM-driven NPC turns have been resolved and before the World
Chronicler is consulted. Its only job is to walk the NPCs currently
in the player's scene, match each against a default daily schedule
keyed off their ``occupation``, and evict any NPC whose schedule
says they are *not* present at the current ``game_state.game_time``.

Evicted NPCs show up in :attr:`TurnOutputs.npc_departures`, which the
:class:`cast.narrator.Narrator` renders as ``Someone departs: ...``
lines in the final prose. The field was shipped dormant in PR #61
(World Chronicler) specifically so that PR #63 only had to populate
it.

Callers can pass ``skip_uuids`` to :meth:`NPCTicker.tick` to shield a
set of NPCs from eviction for a single turn. :class:`PlanExecutor`
uses this to exclude NPCs that were *generated* this very turn —
without it, a bartender placed in a morning tavern by the Scene
Builder would be evicted before the Narrator ever describes them as
present, producing ``Someone departs: Marco is still asleep...`` for
a character the player has never met.

No LLM calls, no schema, no persistence: every decision is a pure
function of ``game_state.game_time`` + each NPC's ``occupation``, so
the ticker works for NPCs that existed before PR #63 as well as new
ones, without any migration. Follow-up PRs can attach per-NPC
overrides or route schedule generation through the NPC Generator; the
surface area here is deliberately small.
"""

from __future__ import annotations

import types
from collections.abc import Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from typing import Any

from cast.schemas import turn_outputs
from models.game_state import GameState

_MORNING = "morning"
_AFTERNOON = "afternoon"
_EVENING = "evening"
_NIGHT = "night"


@dataclass(frozen=True)
class NPCScheduleSlot:
    """One time-of-day slot in an NPC's daily schedule.

    When ``present`` is True the NPC stays in whichever scene they are
    already in and ``activity`` is ignored. When ``present`` is False
    the ticker evicts them and uses ``activity`` as the human-readable
    departure line for the Narrator (e.g. ``"heads off to the
    barracks for the night watch"``).
    """

    present: bool
    activity: str = ""


# A full daily schedule: one slot per time-of-day label used by
# :meth:`GameState.advance_clock`. Keys match ``game_state.game_time``.
# Declared as a read-only ``Mapping`` rather than a mutable ``dict``
# because the concrete values are ``types.MappingProxyType`` wrappers
# chosen to prevent any accidental runtime mutation of the default
# tables.
DailySchedule = Mapping[str, NPCScheduleSlot]

# Singleton "present and doing the thing you were already doing" slot.
# Reused across every schedule so the ``(present=True)`` expression
# never needs to appear in the table bodies.
_PRESENT = NPCScheduleSlot(present=True)

_BARTENDER_MORNING = NPCScheduleSlot(
    present=False,
    activity="is still asleep upstairs after a long night behind the bar",
)
_BARTENDER_AFTERNOON = NPCScheduleSlot(
    present=False,
    activity="slips out to the market for supplies before the evening rush",
)
_GUARD_NIGHT = NPCScheduleSlot(
    present=False,
    activity="heads off to the barracks for the night watch",
)
_MARKET_CLOSED = NPCScheduleSlot(
    present=False,
    activity="packs up the stall and walks home for supper",
)
_BAKER_AFTERNOON = NPCScheduleSlot(
    present=False,
    activity="shutters the bakery once the morning bread is gone",
)
_BAKER_NIGHT = NPCScheduleSlot(
    present=False,
    activity="heads home to rest before the pre-dawn bake",
)


_ALWAYS_PRESENT: DailySchedule = types.MappingProxyType(
    {
        _MORNING: _PRESENT,
        _AFTERNOON: _PRESENT,
        _EVENING: _PRESENT,
        _NIGHT: _PRESENT,
    },
)


_TAVERN_SCHEDULE: DailySchedule = types.MappingProxyType(
    {
        _MORNING: _BARTENDER_MORNING,
        _AFTERNOON: _BARTENDER_AFTERNOON,
        _EVENING: _PRESENT,
        _NIGHT: _PRESENT,
    },
)


_DAY_SHIFT_SCHEDULE: DailySchedule = types.MappingProxyType(
    {
        _MORNING: _PRESENT,
        _AFTERNOON: _PRESENT,
        _EVENING: _PRESENT,
        _NIGHT: _GUARD_NIGHT,
    },
)


_MARKET_SCHEDULE: DailySchedule = types.MappingProxyType(
    {
        _MORNING: _PRESENT,
        _AFTERNOON: _PRESENT,
        _EVENING: _MARKET_CLOSED,
        _NIGHT: _MARKET_CLOSED,
    },
)


_BAKERY_SCHEDULE: DailySchedule = types.MappingProxyType(
    {
        _MORNING: _PRESENT,
        _AFTERNOON: _BAKER_AFTERNOON,
        _EVENING: _BAKER_NIGHT,
        _NIGHT: _BAKER_NIGHT,
    },
)


_DEFAULT_SCHEDULES: types.MappingProxyType[str, DailySchedule] = types.MappingProxyType(
    {
        "bartender": _TAVERN_SCHEDULE,
        "barmaid": _TAVERN_SCHEDULE,
        "innkeeper": _TAVERN_SCHEDULE,
        "tavern keeper": _TAVERN_SCHEDULE,
        "guard": _DAY_SHIFT_SCHEDULE,
        "watchman": _DAY_SHIFT_SCHEDULE,
        "soldier": _DAY_SHIFT_SCHEDULE,
        "merchant": _MARKET_SCHEDULE,
        "shopkeeper": _MARKET_SCHEDULE,
        "trader": _MARKET_SCHEDULE,
        "farmer": _MARKET_SCHEDULE,
        "baker": _BAKERY_SCHEDULE,
    },
)


def get_schedule_for(occupation: str | None) -> DailySchedule:
    """Return the default daily schedule for an NPC ``occupation``.

    Unknown or empty occupations fall back to the always-present
    schedule, which means the ticker becomes a no-op for that NPC.
    Matching is case-insensitive on a stripped occupation string.
    """
    key = (occupation or "").strip().lower()
    return _DEFAULT_SCHEDULES.get(key, _ALWAYS_PRESENT)


def _departure_line(npc: Any, slot: NPCScheduleSlot) -> str:
    """Render a departure line that reads naturally under ``Someone departs:``."""
    occupation = (npc.occupation or "").strip()
    label = "{0} ({1})".format(npc.name, occupation) if occupation else npc.name
    activity = slot.activity or "steps away"
    return "{0} {1}".format(label, activity)


class NPCTicker:
    """Deterministic NPC departure resolver.

    Holds a reference to the live :class:`GameState`; callers invoke
    :meth:`tick` once per turn from
    :class:`cast.director_execution.PlanExecutor`.
    """

    def __init__(self, game_state: GameState) -> None:
        self._gs = game_state

    def tick(
        self,
        raw_outputs: turn_outputs.TurnOutputs,
        skip_uuids: set[str] | None = None,
    ) -> None:
        """Evict schedule-absent NPCs from the current scene.

        ``skip_uuids`` is an optional set of NPC UUIDs to shield from
        eviction for this tick only. :class:`PlanExecutor` populates
        it with NPCs that were *generated this very turn* so that a
        freshly-placed bartender in a morning tavern is not evicted
        before the Narrator ever describes them as present.

        Mutations (all in place):

        * ``game_state.current_scene.npcs_present`` — filtered down
          to the NPCs that remain present at the current time of day.
        * ``raw_outputs.npc_departures`` — extended with one
          human-readable line per evicted NPC. The list is *appended*
          to rather than replaced, so the ticker composes with any
          other future producer of departure lines without stomping
          on its output.

        This method is a no-op when there is no current scene, when
        the scene has no NPCs, or when every NPC's schedule says
        "present" for the current ``game_time``. It never calls the
        LLM and never raises on missing NPC records — unknown UUIDs
        are silently kept in place so a stale ``SceneNPC`` cannot
        wedge the turn.
        """
        scene = self._gs.current_scene
        if scene is None or not scene.npcs_present:
            return

        remaining, departures = self._partition(
            scene.npcs_present,
            self._gs.game_time,
            skip_uuids or frozenset(),
        )
        if not departures:
            return

        scene.npcs_present = remaining
        raw_outputs.npc_departures.extend(departures)

    def _partition(
        self,
        scene_npcs: list[Any],
        time_of_day: str,
        skip_uuids: AbstractSet[str],
    ) -> tuple[list[Any], list[str]]:
        """Split scene NPCs into (kept, departure_lines).

        Any NPC whose ``uuid`` appears in ``skip_uuids`` is kept
        unconditionally — used to shield same-turn-generated NPCs
        from immediate eviction.
        """
        remaining: list[Any] = []
        departures: list[str] = []
        for snpc in scene_npcs:
            if snpc.uuid is not None and snpc.uuid in skip_uuids:
                remaining.append(snpc)
                continue
            line = self._classify(snpc, time_of_day)
            if line is None:
                remaining.append(snpc)
            else:
                departures.append(line)
        return remaining, departures

    def _classify(self, snpc: Any, time_of_day: str) -> str | None:
        """Return a departure line if this scene-NPC should leave, else None."""
        if snpc.uuid is None:
            return None
        npc = self._gs.npcs.get(snpc.uuid)
        if npc is None:
            return None
        slot = get_schedule_for(npc.occupation).get(time_of_day)
        if slot is None or slot.present:
            return None
        return _departure_line(npc, slot)
