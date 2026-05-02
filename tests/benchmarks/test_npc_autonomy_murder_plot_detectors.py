"""Unit tests for the NPC-autonomy murder-plot rubric detectors.

The integration test in ``test_scenarios`` hits paid LLMs (opt-in via the
``benchmark`` marker). These fast unit tests guard the detector logic
that scores a run — in particular the regression where a concealed-
weapon description falsely fired the ``clash_occurred`` predicate.
"""

from __future__ import annotations

import pytest

from benchmarks.harness.types._captures import CapturedTurn
from benchmarks.scenarios.npc_autonomy_murder_plot._detectors import (
    scan_turn_for_clash,
    snapshot_harm_reason,
)
from benchmarks.scenarios.npc_autonomy_murder_plot._node_checks import (
    node_brutus_dead,
    node_marcus_dead,
    node_mentions_both,
)
from benchmarks.scenarios.npc_autonomy_murder_plot.state import (
    BRUTUS_NAME,
    BRUTUS_UUID,
    MARCUS_NAME,
    MARCUS_UUID,
    build_state,
)
from cast.schemas.turn_outputs import DialogueEntry, NPCTurnEntry, TurnOutputs
from knowledge.node import CanonSource, KnowledgeNode, KnowledgeScope, KnowledgeSource
from models.game_state import GameState
from tests._uuid_helpers import make_uuid

_HEALTHY = "healthy"


def _turn(
    *,
    index: int = 0,
    npc_turns: list[NPCTurnEntry] | None = None,
    dialogue: list[DialogueEntry] | None = None,
) -> CapturedTurn:
    outputs = TurnOutputs(npc_turns=npc_turns or [], dialogue=dialogue or [])
    return CapturedTurn(
        index=index,
        player_action="I wait.",
        narration="",
        turn_outputs=outputs,
        duration_ms=0,
    )


def _brutus_entry(action: str, action_type: str) -> NPCTurnEntry:
    return NPCTurnEntry(npc_name=BRUTUS_NAME, action=action, action_type=action_type)


def _state_with_status(*, brutus_status: str, marcus_status: str) -> GameState:
    state = build_state().game_state
    state.npcs[BRUTUS_UUID].physical_status = brutus_status
    state.npcs[MARCUS_UUID].physical_status = marcus_status
    return state


def _city_node(text: str) -> KnowledgeNode:
    return KnowledgeNode(
        text=text,
        scope=KnowledgeScope.CITY,
        source=KnowledgeSource.PERSONAL_EXPERIENCE,
        canon=CanonSource.SESSION,
        location_id=make_uuid("loc"),
        tags=[],
    )


class TestScanTurnForClash:
    def test_passive_stealth_with_pugio_skipped(self):
        entry = _brutus_entry(
            "I keep my gaze on Marcus, my right hand hidden under the tunic where the pugio lies.",
            "STEALTH",
        )
        assert scan_turn_for_clash(_turn(npc_turns=[entry])) is None

    def test_idle_with_weapon_possession_skipped(self):
        entry = _brutus_entry(
            "I nurse my cup and watch Marcus across the room; my blade stays hidden.",
            "IDLE",
        )
        assert scan_turn_for_clash(_turn(npc_turns=[entry])) is None

    def test_attack_action_type_fires(self):
        entry = _brutus_entry("I move on him.", "ATTACK")
        reason = scan_turn_for_clash(_turn(npc_turns=[entry]))
        assert reason is not None
        assert "ATTACK" in reason

    def test_active_verb_against_marcus_fires(self):
        entry = _brutus_entry("I lunge at Marcus with the pugio drawn.", "STEALTH")
        reason = scan_turn_for_clash(_turn(npc_turns=[entry]))
        assert reason is not None
        assert "lunge" in reason.lower() or "marcus" in reason.lower()

    def test_verb_without_marcus_skipped(self):
        entry = _brutus_entry("I stab my knife into the bench in frustration.", "STEALTH")
        assert scan_turn_for_clash(_turn(npc_turns=[entry])) is None

    def test_contest_roll_between_pair_fires(self):
        dialogue = DialogueEntry(
            npc_name=MARCUS_NAME,
            response="He steps back!",
            contest_roll="Brutus vs Marcus combat: success for Brutus.",
        )
        reason = scan_turn_for_clash(_turn(dialogue=[dialogue]))
        assert reason is not None
        assert "contest_roll" in reason

    def test_non_brutus_attack_ignored(self):
        entry = NPCTurnEntry(npc_name="some bystander", action="I stab Marcus.", action_type="ATTACK")
        assert scan_turn_for_clash(_turn(npc_turns=[entry])) is None


class TestSnapshotHarmReason:
    def test_both_healthy_returns_none(self):
        before = build_state().game_state
        after = _state_with_status(brutus_status=_HEALTHY, marcus_status=_HEALTHY)
        assert snapshot_harm_reason([before, after]) is None

    def test_marcus_wounded_reports_target(self):
        before = build_state().game_state
        after = _state_with_status(brutus_status=_HEALTHY, marcus_status="wounded, bleeding from chest")
        reason = snapshot_harm_reason([before, after])
        assert reason is not None
        assert "Marcus" in reason

    def test_brutus_dead_reports_attacker(self):
        before = build_state().game_state
        after = _state_with_status(brutus_status="dead", marcus_status=_HEALTHY)
        reason = snapshot_harm_reason([before, after])
        assert reason is not None
        assert "Brutus" in reason

    def test_marcus_removed_reports_absence(self):
        before = build_state().game_state
        after = _state_with_status(brutus_status=_HEALTHY, marcus_status=_HEALTHY)
        after.npcs.pop(MARCUS_UUID)
        reason = snapshot_harm_reason([before, after])
        assert reason is not None
        assert "Marcus absent" in reason

    def test_empty_snapshots_returns_none(self):
        assert snapshot_harm_reason([]) is None


class TestNodeChecks:
    @pytest.fixture()
    def marcus_death_node(self) -> KnowledgeNode:
        return _city_node("Marcus was killed by Brutus in the Forum Taberna.")

    def test_marcus_dead_fires_on_city_death(self, marcus_death_node):
        assert node_marcus_dead(marcus_death_node) is True

    def test_brutus_dead_fires_on_city_death(self):
        assert node_brutus_dead(_city_node("Brutus died in the clash, mortally wounded.")) is True

    def test_marcus_dead_false_for_local_scope(self):
        local = KnowledgeNode(
            text="Marcus was killed.",
            scope=KnowledgeScope.LOCAL,
            source=KnowledgeSource.PERSONAL_EXPERIENCE,
            canon=CanonSource.SESSION,
            location_id=make_uuid("loc"),
            tags=[],
        )
        assert node_marcus_dead(local) is False

    def test_mentions_both_true_when_named(self):
        assert node_mentions_both("Brutus stared at Marcus across the room.") is True

    def test_mentions_both_false_when_only_one(self):
        assert node_mentions_both("Marcus sipped his wine alone.") is False
