"""Tests for :mod:`cast.npc_ticker` — schedule-driven NPC departures."""

from __future__ import annotations

from uuid import UUID

import allure
import pytest

from cast.npc_ticker import (
    NPCScheduleSlot,
    NPCTicker,
    _ALWAYS_PRESENT,
    _DAY_SHIFT_SCHEDULE,
    _TAVERN_SCHEDULE,
    get_schedule_for,
)
from cast.schemas.turn_outputs import TurnOutputs
from knowledge.graph import KnowledgeGraph
from models import game_state as _gs, goal as _goal, npc_card as _npc, scene as _scene, setting as _setting
from tests._uuid_helpers import make_uuid

GameState = _gs.GameState
Goal = _goal.Goal
GoalKind = _goal.GoalKind
GoalScope = _goal.GoalScope
NPCCard = _npc.NPCCard
Scene = _scene.Scene
SceneNPC = _scene.SceneNPC
Setting = _setting.Setting

_BARTENDER_UUID = make_uuid("npc-bartender")
_GUARD_UUID = make_uuid("npc-guard")
_BAKER_UUID = make_uuid("npc-baker")
_UNKNOWN_UUID = make_uuid("npc-unknown")


def _make_game_state(game_time: str = "morning") -> GameState:
    gs = GameState(
        setting=Setting(name="Rome", time_period="1 AD", region="Italy", summary=""),
        knowledge_graph=KnowledgeGraph(),
    )
    gs.game_time = game_time
    return gs


def _add_npc(gs: GameState, uuid: UUID, name: str, occupation: str, *, introduced: bool = False) -> NPCCard:
    npc = NPCCard(name=name, occupation=occupation)
    npc.uuid = uuid
    gs.npcs[uuid] = npc
    if introduced:
        gs.player.known_npcs.add(uuid)
    return npc


def _set_scene(gs: GameState, *npc_uuids: UUID) -> Scene:
    scene = Scene(
        location_id=make_uuid("tavern"),
        description="The Rusty Anchor tavern.",
        npcs_present=[SceneNPC(role="npc", uuid=uid) for uid in npc_uuids],
    )
    gs.current_scene = scene
    return scene


@allure.epic("NPC Interaction")
@allure.feature("NPC schedule ticker")
class TestGetScheduleFor:
    @allure.story("Occupation lookup")
    @allure.title("Unknown occupation falls back to the always-present schedule")
    def test_unknown_occupation_falls_back_to_always_present(self):
        assert get_schedule_for("wizard") is _ALWAYS_PRESENT

    @allure.story("Occupation lookup")
    @allure.title("Empty and None occupations fall back to the always-present schedule")
    def test_empty_occupation_falls_back(self):
        assert get_schedule_for("") is _ALWAYS_PRESENT
        assert get_schedule_for(None) is _ALWAYS_PRESENT

    @allure.story("Occupation lookup")
    @allure.title("Known occupations are matched case-insensitively after stripping")
    def test_matching_is_case_insensitive(self):
        assert get_schedule_for("Bartender") is _TAVERN_SCHEDULE
        assert get_schedule_for("  GUARD  ") is _DAY_SHIFT_SCHEDULE

    @allure.story("Occupation lookup")
    @allure.title("Multiple aliases (bartender / innkeeper / tavern keeper) share the tavern schedule")
    def test_tavern_aliases_share_schedule(self):
        assert get_schedule_for("innkeeper") is _TAVERN_SCHEDULE
        assert get_schedule_for("tavern keeper") is _TAVERN_SCHEDULE
        assert get_schedule_for("barmaid") is _TAVERN_SCHEDULE


@allure.epic("NPC Interaction")
@allure.feature("NPC schedule ticker")
class TestNPCTickerNoOp:
    @allure.story("No-op paths")
    @allure.title("tick() is a no-op when there is no current scene")
    def test_no_scene_is_no_op(self):
        gs = _make_game_state()
        ticker = NPCTicker(gs)
        outputs = TurnOutputs()
        ticker.tick(outputs)
        assert outputs.npc_departures == []

    @allure.story("No-op paths")
    @allure.title("tick() is a no-op when the scene has no NPCs")
    def test_empty_scene_is_no_op(self):
        gs = _make_game_state()
        _set_scene(gs)  # no NPCs
        outputs = TurnOutputs()
        NPCTicker(gs).tick(outputs)
        assert outputs.npc_departures == []

    @allure.story("No-op paths")
    @allure.title("tick() leaves every always-present NPC in place regardless of time of day")
    def test_always_present_npcs_are_kept(self):
        gs = _make_game_state(game_time="night")
        priest = make_uuid("npc-priest")
        beggar = make_uuid("npc-beggar")
        _add_npc(gs, priest, "Paolo", "priest")
        _add_npc(gs, beggar, "Benno", "beggar")
        scene = _set_scene(gs, priest, beggar)

        outputs = TurnOutputs()
        NPCTicker(gs).tick(outputs)

        assert outputs.npc_departures == []
        assert [snpc.uuid for snpc in scene.npcs_present] == [priest, beggar]

    @allure.story("No-op paths")
    @allure.title("tick() silently keeps SceneNPCs whose UUID is missing from game_state.npcs")
    def test_missing_npc_record_is_kept(self):
        gs = _make_game_state(game_time="night")
        scene = _set_scene(gs, _UNKNOWN_UUID)  # no matching NPCCard registered

        outputs = TurnOutputs()
        NPCTicker(gs).tick(outputs)

        assert outputs.npc_departures == []
        assert [snpc.uuid for snpc in scene.npcs_present] == [_UNKNOWN_UUID]

    @allure.story("No-op paths")
    @allure.title("tick() silently keeps SceneNPCs whose uuid is None (uninitialised)")
    def test_uninitialised_scene_npc_is_kept(self):
        gs = _make_game_state(game_time="night")
        scene = Scene(
            location_id=make_uuid("tavern"),
            description="x",
            npcs_present=[SceneNPC(role="stranger", uuid=None)],
        )
        gs.current_scene = scene

        outputs = TurnOutputs()
        NPCTicker(gs).tick(outputs)

        assert outputs.npc_departures == []
        assert len(scene.npcs_present) == 1


@allure.epic("NPC Interaction")
@allure.feature("NPC schedule ticker")
class TestNPCTickerEvictions:
    @allure.story("Eviction")
    @allure.title("A bartender in the tavern in the morning is evicted with an activity line")
    def test_bartender_evicted_in_morning(self):
        gs = _make_game_state(game_time="morning")
        _add_npc(gs, _BARTENDER_UUID, "Marco", "bartender", introduced=True)
        scene = _set_scene(gs, _BARTENDER_UUID)

        outputs = TurnOutputs()
        NPCTicker(gs).tick(outputs)

        assert scene.npcs_present == []
        assert len(outputs.npc_departures) == 1
        line = outputs.npc_departures[0]
        assert line.startswith("Marco (bartender)")
        assert "asleep" in line

    @allure.story("Eviction")
    @allure.title("A guard is evicted at night with the night-watch activity line")
    def test_guard_evicted_at_night(self):
        gs = _make_game_state(game_time="night")
        _add_npc(gs, _GUARD_UUID, "Lucia", "guard", introduced=True)
        scene = _set_scene(gs, _GUARD_UUID)

        outputs = TurnOutputs()
        NPCTicker(gs).tick(outputs)

        assert scene.npcs_present == []
        assert outputs.npc_departures == ["Lucia (guard) heads off to the barracks for the night watch"]

    @allure.story("Eviction")
    @allure.title("A guard in the morning stays in the scene (day shift is present)")
    def test_guard_present_in_morning(self):
        gs = _make_game_state(game_time="morning")
        _add_npc(gs, _GUARD_UUID, "Lucia", "guard")
        scene = _set_scene(gs, _GUARD_UUID)

        outputs = TurnOutputs()
        NPCTicker(gs).tick(outputs)

        assert outputs.npc_departures == []
        assert [snpc.uuid for snpc in scene.npcs_present] == [_GUARD_UUID]

    @allure.story("Eviction")
    @allure.title("NPC with active tactical goal is shielded from schedule eviction")
    def test_active_tactical_goal_shields_from_eviction(self):
        gs = _make_game_state(game_time="night")
        guard = _add_npc(gs, _GUARD_UUID, "Lucia", "guard")
        guard.tactical_goal = Goal(
            scope=GoalScope.TACTICAL,
            kind=GoalKind.DEFEND,
            description="hold ground against the player",
        )
        scene = _set_scene(gs, _GUARD_UUID)

        outputs = TurnOutputs()
        NPCTicker(gs).tick(outputs)

        assert outputs.npc_departures == []
        assert [snpc.uuid for snpc in scene.npcs_present] == [_GUARD_UUID]

    @allure.story("Eviction")
    @allure.title("Mixed scene: only the schedule-absent NPCs are evicted; present ones stay")
    def test_mixed_scene_partial_eviction(self):
        gs = _make_game_state(game_time="night")
        _add_npc(gs, _BARTENDER_UUID, "Marco", "bartender")  # present at night → stays
        _add_npc(gs, _GUARD_UUID, "Lucia", "guard", introduced=True)  # absent at night → evicted
        _add_npc(gs, _BAKER_UUID, "Bruno", "baker", introduced=True)  # absent at night → evicted
        scene = _set_scene(gs, _BARTENDER_UUID, _GUARD_UUID, _BAKER_UUID)

        outputs = TurnOutputs()
        NPCTicker(gs).tick(outputs)

        assert [snpc.uuid for snpc in scene.npcs_present] == [_BARTENDER_UUID]
        assert len(outputs.npc_departures) == 2
        assert any("Lucia" in line for line in outputs.npc_departures)
        assert any("Bruno" in line for line in outputs.npc_departures)

    @allure.story("Eviction")
    @allure.title("tick() extends an existing npc_departures list without replacing it")
    def test_extends_existing_departures(self):
        gs = _make_game_state(game_time="night")
        _add_npc(gs, _GUARD_UUID, "Lucia", "guard", introduced=True)
        _set_scene(gs, _GUARD_UUID)

        outputs = TurnOutputs(npc_departures=["A stranger slips out the back door"])
        NPCTicker(gs).tick(outputs)

        assert len(outputs.npc_departures) == 2
        assert outputs.npc_departures[0] == "A stranger slips out the back door"
        assert "Lucia" in outputs.npc_departures[1]

    @allure.story("Eviction")
    @allure.title("A second tick() on the same scene is idempotent once departures already ran")
    def test_second_tick_is_idempotent(self):
        gs = _make_game_state(game_time="night")
        _add_npc(gs, _GUARD_UUID, "Lucia", "guard")
        _set_scene(gs, _GUARD_UUID)

        ticker = NPCTicker(gs)
        outputs_a = TurnOutputs()
        ticker.tick(outputs_a)
        outputs_b = TurnOutputs()
        ticker.tick(outputs_b)

        assert len(outputs_a.npc_departures) == 1
        assert outputs_b.npc_departures == []


@allure.epic("NPC Interaction")
@allure.feature("NPC schedule ticker")
class TestNPCTickerSkipUuids:
    @allure.story("Skip uuids")
    @allure.title("skip_uuids shields a would-be-evicted NPC from removal")
    def test_skip_uuids_prevents_eviction(self):
        gs = _make_game_state(game_time="morning")
        _add_npc(gs, _BARTENDER_UUID, "Marco", "bartender")
        scene = _set_scene(gs, _BARTENDER_UUID)

        outputs = TurnOutputs()
        NPCTicker(gs).tick(outputs, skip_uuids={_BARTENDER_UUID})

        assert [snpc.uuid for snpc in scene.npcs_present] == [_BARTENDER_UUID]
        assert outputs.npc_departures == []

    @allure.story("Skip uuids")
    @allure.title("skip_uuids default of None preserves the original eviction behaviour")
    def test_skip_uuids_default_none_preserves_eviction(self):
        gs = _make_game_state(game_time="morning")
        _add_npc(gs, _BARTENDER_UUID, "Marco", "bartender")
        scene = _set_scene(gs, _BARTENDER_UUID)

        outputs = TurnOutputs()
        NPCTicker(gs).tick(outputs)  # no skip_uuids

        assert scene.npcs_present == []
        assert len(outputs.npc_departures) == 1

    @allure.story("Skip uuids")
    @allure.title("skip_uuids shields only the listed NPCs; others are still evicted")
    def test_skip_uuids_partial_shield(self):
        gs = _make_game_state(game_time="night")
        _add_npc(gs, _GUARD_UUID, "Lucia", "guard")  # absent at night → would be evicted (shielded below)
        _add_npc(gs, _BAKER_UUID, "Bruno", "baker", introduced=True)  # absent at night → evicted
        scene = _set_scene(gs, _GUARD_UUID, _BAKER_UUID)

        outputs = TurnOutputs()
        NPCTicker(gs).tick(outputs, skip_uuids={_GUARD_UUID})

        assert [snpc.uuid for snpc in scene.npcs_present] == [_GUARD_UUID]
        assert len(outputs.npc_departures) == 1
        assert "Bruno" in outputs.npc_departures[0]

    @allure.story("Skip uuids")
    @allure.title("An empty skip_uuids set behaves identically to the default (None)")
    def test_empty_skip_uuids_is_noop_on_skip(self):
        gs = _make_game_state(game_time="morning")
        _add_npc(gs, _BARTENDER_UUID, "Marco", "bartender")
        scene = _set_scene(gs, _BARTENDER_UUID)

        outputs = TurnOutputs()
        NPCTicker(gs).tick(outputs, skip_uuids=set())

        assert scene.npcs_present == []
        assert len(outputs.npc_departures) == 1


@allure.epic("NPC Interaction")
@allure.feature("NPC schedule ticker")
class TestNPCTickerNameGating:
    """Departure lines must gate proper names on ``player.known_npcs``.

    Regression: :func:`cast.npc_ticker._departure_line` built the label
    from the raw ``npc.name``, bypassing the ``known_npcs`` gate that
    every other Narrator-bound producer (``new_npcs``, on-shift labels,
    scene ``people visible``) already enforces — so an unintroduced
    NPC's proper name leaked into the Narrator's ``Someone departs:``
    line before the player had ever met them.
    """

    @allure.story("Name gating")
    @allure.title("An unintroduced NPC's departure line hides the proper name behind the role")
    def test_unintroduced_departure_hides_name(self):
        gs = _make_game_state(game_time="morning")
        _add_npc(gs, _BARTENDER_UUID, "Marco", "bartender")  # never introduced to the player
        _set_scene(gs, _BARTENDER_UUID)

        outputs = TurnOutputs()
        NPCTicker(gs).tick(outputs)

        line = outputs.npc_departures[0]
        assert "Marco" not in line
        assert "bartender" in line
        assert "asleep" in line

    @allure.story("Name gating")
    @allure.title("An unintroduced NPC with a short_descriptor departs as that descriptor")
    def test_unintroduced_departure_uses_descriptor(self):
        gs = _make_game_state(game_time="morning")
        npc = _add_npc(gs, _BARTENDER_UUID, "Marco", "bartender")
        npc.short_descriptor = "a curly-haired man"
        _set_scene(gs, _BARTENDER_UUID)

        outputs = TurnOutputs()
        NPCTicker(gs).tick(outputs)

        line = outputs.npc_departures[0]
        assert "Marco" not in line
        assert line.startswith("a curly-haired man")

    @allure.story("Name gating")
    @allure.title("An introduced NPC's departure line still shows the Name (Occupation) shape")
    def test_introduced_departure_shows_name(self):
        gs = _make_game_state(game_time="morning")
        _add_npc(gs, _BARTENDER_UUID, "Marco", "bartender", introduced=True)  # player has met Marco
        _set_scene(gs, _BARTENDER_UUID)

        outputs = TurnOutputs()
        NPCTicker(gs).tick(outputs)

        assert outputs.npc_departures[0].startswith("Marco (bartender)")


@allure.epic("NPC Interaction")
@allure.feature("NPC schedule ticker")
class TestNPCScheduleSlot:
    @allure.story("Data model")
    @allure.title("NPCScheduleSlot defaults activity to an empty string and is hashable (frozen)")
    def test_slot_defaults(self):
        slot = NPCScheduleSlot(present=True)
        assert slot.activity == ""
        # Frozen dataclasses are hashable
        assert hash(slot) == hash(NPCScheduleSlot(present=True))

    @allure.story("Data model")
    @allure.title("NPCScheduleSlot rejects mutation — frozen dataclass")
    def test_slot_is_frozen(self):
        slot = NPCScheduleSlot(present=True, activity="x")
        with pytest.raises(Exception):
            slot.present = False  # type: ignore[misc]
