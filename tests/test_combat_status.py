"""Tests for combat status hints and recovery event scheduling."""

from __future__ import annotations

import random

import pytest

from cast.dice import CombatOutcome
from cast.director_dialogue_helpers import build_combat_action
from cast.director_dialogue import _schedule_recovery
from models.npc_card import NPCCard
from models.setting import Setting
from knowledge.graph import KnowledgeGraph
from models.game_state import GameState
from timeline.event_manager import EventManager

_GUARD_NAME = "Guard"
_GUARD_OCC = "guard"
_STATUS_TAG = "[STATUS:"
_COMBAT_SKILL = "combat_skill"
_RNG_SEED = 57005


def _make_game_state() -> GameState:
    kg = KnowledgeGraph()
    return GameState(
        setting=Setting(name="Rome", time_period="1 AD", region="Italy", summary=""),
        knowledge_graph=kg,
    )


def _make_guard(**kwargs) -> NPCCard:
    return NPCCard(name=_GUARD_NAME, occupation=_GUARD_OCC, **kwargs)


class TestBuildCombatActionStatusHint:
    def test_player_succeeds_includes_status_hint(self):
        npc = _make_guard(attributes={_COMBAT_SKILL: 0})
        rng = random.Random(_RNG_SEED)
        action_text, combat_roll = build_combat_action("slash the guard", npc, True, _rng=rng)
        if combat_roll and combat_roll.outcome in (
            CombatOutcome.PLAYER_SUCCEEDS,
            CombatOutcome.PLAYER_DOMINATES,
        ):
            assert _STATUS_TAG in action_text

    def test_non_aggressive_no_status_hint(self):
        npc = _make_guard()
        action_text, combat_roll = build_combat_action("hello guard", npc, False)
        assert _STATUS_TAG not in action_text
        assert combat_roll is None

    def test_npc_wins_no_status_hint(self):
        npc = _make_guard(attributes={_COMBAT_SKILL: 10})
        for seed in range(100):
            rng = random.Random(seed)
            action_text, combat_roll = build_combat_action("attack guard", npc, True, _rng=rng)
            if combat_roll and combat_roll.outcome in (
                CombatOutcome.NPC_OVERPOWERS,
                CombatOutcome.NPC_DEFENDS,
            ):
                assert _STATUS_TAG not in action_text
                return
        pytest.skip("Could not find a seed where NPC wins")


class TestScheduleRecovery:
    def test_schedules_recovery_for_wounded_npc(self):
        gs = _make_game_state()
        npc = _make_guard(physical_status="wounded")
        gs.npcs[npc.uuid] = npc
        event_mgr = EventManager(game_state=gs, knowledge_graph=gs.knowledge_graph)

        event = _schedule_recovery(
            npc=npc,
            combat_outcome=CombatOutcome.PLAYER_SUCCEEDS,
            game_state=gs,
            event_manager=event_mgr,
        )
        assert event is not None
        assert event.effects[0].effect_type == "CHANGE_STATUS"
        assert event.effects[0].effect_data["status"] == "healthy"

    def test_dominates_has_longer_recovery(self):
        gs = _make_game_state()
        npc = _make_guard(physical_status="badly hurt")
        gs.npcs[npc.uuid] = npc
        event_mgr = EventManager(game_state=gs, knowledge_graph=gs.knowledge_graph)

        event_succeed = _schedule_recovery(
            npc=npc,
            combat_outcome=CombatOutcome.PLAYER_SUCCEEDS,
            game_state=gs,
            event_manager=event_mgr,
        )
        event_dominate = _schedule_recovery(
            npc=npc,
            combat_outcome=CombatOutcome.PLAYER_DOMINATES,
            game_state=gs,
            event_manager=event_mgr,
        )
        assert event_dominate.duration > event_succeed.duration

    def test_no_recovery_when_npc_wins(self):
        gs = _make_game_state()
        npc = _make_guard()
        gs.npcs[npc.uuid] = npc
        event_mgr = EventManager(game_state=gs, knowledge_graph=gs.knowledge_graph)

        event = _schedule_recovery(
            npc=npc,
            combat_outcome=CombatOutcome.NPC_DEFENDS,
            game_state=gs,
            event_manager=event_mgr,
        )
        assert event is None

    def test_no_recovery_when_status_is_healthy(self):
        gs = _make_game_state()
        npc = _make_guard(physical_status="healthy")
        gs.npcs[npc.uuid] = npc
        event_mgr = EventManager(game_state=gs, knowledge_graph=gs.knowledge_graph)

        event = _schedule_recovery(
            npc=npc,
            combat_outcome=CombatOutcome.PLAYER_SUCCEEDS,
            game_state=gs,
            event_manager=event_mgr,
        )
        assert event is None
