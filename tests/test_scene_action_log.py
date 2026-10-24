"""Tests for the per-scene action log and its append helpers."""

from __future__ import annotations

from dataclasses import dataclass

import allure
import pytest
from pydantic import ValidationError

from cast import scene_log as scene_log_mod
from knowledge.graph import KnowledgeGraph
from models.game_state import GameState
from models.npc_card import NPCCard
from models.scene_action_log import ActorKind, SceneActionEntry, this_turn_npc_replies
from models.setting import Setting
from tests._uuid_helpers import make_uuid

_NPC_UUID = make_uuid("npc-marcus")
_TARGET_UUID = make_uuid("npc-target")


def _make_gs() -> GameState:
    return GameState(
        setting=Setting(name="Rome", time_period="1 AD", region="Italy", summary=""),
        knowledge_graph=KnowledgeGraph(),
    )


def _make_npc() -> NPCCard:
    npc = NPCCard(name="Marcus", occupation="guard")
    npc.uuid = _NPC_UUID
    return npc


@dataclass
class _FakeContestRoll:
    outcome: object


@dataclass
class _FakeOutcome:
    value: str


@dataclass
class _FakeNPCAction:
    npc_uuid: object
    npc_name: str
    action_description: str
    action_type: str
    target: object
    contest_roll: object


@allure.epic("NPC short-term memory")
@allure.feature("Scene action log")
class TestSceneActionEntryRoundTrip:
    @allure.story("Persistence")
    @allure.title("SceneActionEntry round-trips through model_dump(mode='json') losslessly")
    def test_json_round_trip_preserves_all_fields(self):
        original = SceneActionEntry(
            actor_kind=ActorKind.NPC,
            actor_uuid=_NPC_UUID,
            actor_name="Marcus",
            action_type="ATTACK",
            description="Marcus draws a dagger.",
            target_uuid=_TARGET_UUID,
            target_name="player",
            game_clock=12.5,
            significant=True,
            metadata={"contest_outcome": "actor_dominates"},
        )
        dumped = original.model_dump(mode="json")
        restored = SceneActionEntry(**dumped)
        assert restored.actor_kind == original.actor_kind
        assert restored.actor_uuid == original.actor_uuid
        assert restored.actor_name == original.actor_name
        assert restored.action_type == original.action_type
        assert restored.description == original.description
        assert restored.target_uuid == original.target_uuid
        assert restored.target_name == original.target_name
        assert restored.game_clock == original.game_clock
        assert restored.significant is True
        assert restored.metadata == original.metadata


@allure.epic("NPC short-term memory")
@allure.feature("Scene action log")
class TestAppendPlayerAction:
    @allure.story("Append helpers")
    @allure.title("append_player_action records action_type and routine TALK is not significant")
    def test_routine_player_talk_not_significant(self):
        gs = _make_gs()
        gs.game_clock = 3.0
        scene_log_mod.append_player_action(gs, "TALK", "I greet the merchant.")
        assert len(gs.scene_action_log) == 1
        entry = gs.scene_action_log[0]
        assert entry.actor_kind == ActorKind.PLAYER
        assert entry.action_type == "TALK"
        assert entry.description == "I greet the merchant."
        assert entry.actor_name == gs.player.name
        assert entry.actor_uuid == gs.player.uuid
        assert entry.game_clock == pytest.approx(3.0)
        assert entry.significant is False

    @allure.story("Append helpers")
    @allure.title("Player aggressive action is flagged significant for scene-end consolidation")
    def test_aggressive_player_action_is_significant(self):
        gs = _make_gs()
        scene_log_mod.append_player_action(gs, "ATTACK", "I lunge at the guard.", is_aggressive=True)
        assert gs.scene_action_log[0].significant is True
        assert gs.scene_action_log[0].metadata.get("player_is_aggressive") is True


@allure.epic("NPC short-term memory")
@allure.feature("Scene action log")
class TestAppendNPCAction:
    @allure.story("Append helpers")
    @allure.title("Routine NPC IDLE is not significant; ATTACK is significant")
    def test_idle_not_significant_attack_is(self):
        gs = _make_gs()
        npc = _make_npc()
        idle = _FakeNPCAction(
            npc_uuid=npc.uuid,
            npc_name=npc.name,
            action_description="Marcus watches the crowd.",
            action_type="IDLE",
            target=None,
            contest_roll=None,
        )
        attack = _FakeNPCAction(
            npc_uuid=npc.uuid,
            npc_name=npc.name,
            action_description="Marcus stabs the merchant.",
            action_type="ATTACK",
            target="Merchant",
            contest_roll=_FakeContestRoll(outcome=_FakeOutcome(value="actor_succeeds")),
        )
        scene_log_mod.append_npc_action(gs, npc, idle)
        scene_log_mod.append_npc_action(gs, npc, attack)
        assert gs.scene_action_log[0].significant is False
        assert gs.scene_action_log[1].significant is True
        assert gs.scene_action_log[1].metadata["contest_outcome"] == "actor_succeeds"
        assert gs.scene_action_log[1].target_name == "Merchant"

    @allure.story("Append helpers")
    @allure.title("Successful INTIMIDATE is significant; resisted INTIMIDATE is not")
    def test_intimidation_outcome_drives_significance(self):
        gs = _make_gs()
        npc = _make_npc()
        won = _FakeNPCAction(
            npc_uuid=npc.uuid,
            npc_name=npc.name,
            action_description="Marcus snarls.",
            action_type="INTIMIDATE",
            target="Merchant",
            contest_roll=_FakeContestRoll(outcome=_FakeOutcome(value="actor_dominates")),
        )
        lost = _FakeNPCAction(
            npc_uuid=npc.uuid,
            npc_name=npc.name,
            action_description="Marcus snarls.",
            action_type="INTIMIDATE",
            target="Merchant",
            contest_roll=_FakeContestRoll(outcome=_FakeOutcome(value="target_resists")),
        )
        scene_log_mod.append_npc_action(gs, npc, won)
        scene_log_mod.append_npc_action(gs, npc, lost)
        assert gs.scene_action_log[0].significant is True
        assert gs.scene_action_log[1].significant is False


@allure.epic("NPC short-term memory")
@allure.feature("Scene action log")
class TestAppendNPCDialogue:
    @allure.story("Append helpers")
    @allure.title("NPC dialogue lands as a TALK entry pointing at the player")
    def test_dialogue_appended_as_talk(self):
        gs = _make_gs()
        npc = _make_npc()
        scene_log_mod.append_npc_dialogue(gs, npc, "I have nothing to say to you.")
        entry = gs.scene_action_log[0]
        assert entry.actor_kind == ActorKind.NPC
        assert entry.action_type == "TALK"
        assert entry.description == "I have nothing to say to you."
        assert entry.target_name == gs.player.name
        assert entry.significant is False


@allure.epic("NPC short-term memory")
@allure.feature("Scene action log")
class TestAppendEvent:
    @allure.story("Append helpers")
    @allure.title("Witnessed events are significant and carry already_persisted flag")
    def test_event_marks_already_persisted(self):
        gs = _make_gs()
        scene_log_mod.append_event(
            gs,
            scene_log_mod.WitnessedEvent(
                event_type="WITNESS",
                description="Player smashes the lantern.",
                witness_ids=[_NPC_UUID],
                already_persisted=True,
            ),
        )
        entry = gs.scene_action_log[0]
        assert entry.actor_kind == ActorKind.EVENT
        assert entry.significant is True
        assert entry.metadata["already_persisted"] is True
        assert str(_NPC_UUID) in entry.metadata["witness_ids"]


@allure.epic("NPC short-term memory")
@allure.feature("Scene action log")
class TestActorKindInvariant:
    """The ``actor_kind`` ↔ ``actor_uuid``/``actor_name`` matrix is enforced.

    Illegal combinations must be rejected at construction (and therefore
    at JSONB rehydration, which goes through ``SceneActionEntry(**raw)``)
    rather than only being maintained by producer convention.
    """

    @allure.story("Type invariants")
    @allure.title("PLAYER entry without an actor_uuid is rejected")
    def test_player_requires_actor_uuid(self):
        with pytest.raises(ValidationError):
            SceneActionEntry(
                actor_kind=ActorKind.PLAYER,
                actor_uuid=None,
                actor_name="Traveller",
                action_type="MOVE",
                description="walks north",
                game_clock=1.0,
            )

    @allure.story("Type invariants")
    @allure.title("NPC entry with an empty actor_name is accepted (name is not invariant-bearing)")
    def test_npc_empty_actor_name_allowed(self):
        # actor_name is derived from npc.name/player.name (defaulted
        # upstream) and every consumer falls back on a blank label;
        # enforcing non-empty here would only add a runtime failure
        # mode. The load-bearing invariant is the actor_uuid presence.
        entry = SceneActionEntry(
            actor_kind=ActorKind.NPC,
            actor_uuid=_NPC_UUID,
            actor_name="",
            action_type="TALK",
            description="says hello",
            game_clock=1.0,
        )
        assert entry.actor_kind == ActorKind.NPC

    @allure.story("Type invariants")
    @allure.title("EVENT entry carrying an actor_uuid or actor_name is rejected")
    def test_event_must_be_anonymous(self):
        with pytest.raises(ValidationError):
            SceneActionEntry(
                actor_kind=ActorKind.EVENT,
                actor_uuid=_NPC_UUID,
                actor_name="",
                action_type="WITNESS",
                description="a lantern shatters",
                game_clock=1.0,
            )
        with pytest.raises(ValidationError):
            SceneActionEntry(
                actor_kind=ActorKind.EVENT,
                actor_uuid=None,
                actor_name="Marcus",
                action_type="WITNESS",
                description="a lantern shatters",
                game_clock=1.0,
            )

    @allure.story("Type invariants")
    @allure.title("Producer-shaped entries for every actor_kind still construct")
    def test_legal_entries_round_trip(self):
        player = SceneActionEntry(
            actor_kind=ActorKind.PLAYER,
            actor_uuid=_NPC_UUID,
            actor_name="Traveller",
            action_type="MOVE",
            description="walks north",
            game_clock=1.0,
        )
        event = SceneActionEntry(
            actor_kind=ActorKind.EVENT,
            actor_uuid=None,
            actor_name="",
            action_type="WITNESS",
            description="a lantern shatters",
            game_clock=1.0,
        )
        assert player.actor_kind == ActorKind.PLAYER
        assert event.actor_kind == ActorKind.EVENT
        assert SceneActionEntry(**event.model_dump()).actor_kind == ActorKind.EVENT


@allure.epic("NPC short-term memory")
@allure.feature("Scene action log")
class TestThisTurnNPCReplies:
    @allure.story("Anti-echo")
    @allure.title("Only NPC TALK entries after the latest player action are returned, in log order")
    def test_returns_this_turns_replies_in_order(self):
        gs = _make_gs()
        npc = _make_npc()
        scene_log_mod.append_player_action(gs, "TALK", "Who are you?")
        scene_log_mod.append_npc_dialogue(gs, npc, "Earlier reply.")
        scene_log_mod.append_player_action(gs, "TALK", "Where am I?")
        scene_log_mod.append_npc_dialogue(gs, npc, "First reply.")
        scene_log_mod.append_npc_action(gs, npc, _FakeNPCAction(npc.uuid, "Marcus", "Shrugs.", "IDLE", None, None))
        scene_log_mod.append_event(gs, scene_log_mod.WitnessedEvent(event_type="WITNESS", description="A bell."))
        scene_log_mod.append_npc_dialogue(gs, npc, "Second reply.")

        replies = this_turn_npc_replies(gs.scene_action_log)

        assert [entry.description for entry in replies] == ["First reply.", "Second reply."]

    @allure.story("Anti-echo")
    @allure.title("A log ending with the player's action has no replies yet")
    def test_no_replies_after_fresh_player_action(self):
        gs = _make_gs()
        scene_log_mod.append_npc_dialogue(gs, _make_npc(), "Old reply.")
        scene_log_mod.append_player_action(gs, "WAIT", "I wait.")

        assert this_turn_npc_replies(gs.scene_action_log) == []
