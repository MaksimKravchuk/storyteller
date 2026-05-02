"""Tests for cast.director_witness — KER-18 regression.

Cover the proximity-witness broadcast for aggressive INTERACT actions
against inanimate targets. When the player smashes a shutter in a
scene that contains a guard, the pipeline must:

* Publish a :class:`WitnessedAggression` onto ``TurnOutputs``.
* Flip the guard's ``current_mood`` from ``"neutral"`` → ``"threatened"``
  (the only semantically accurate mood that is also a registered entry
  in ``cast.dice.AGGRESSION_THRESHOLDS``).
* Leave non-guard occupations (tailors, beggars) alone.
* Inject an INCIDENT clause into ``_build_turn_prompt`` for guards whose
  scene ``location_id`` matches the witnessed event.
* Fire the guard's NPC autonomous turn on the same turn the vandalism
  is committed, so the guard reacts within 1 turn of the smash-kick
  loop the Ancient Rome playtest flagged.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import allure
import pytest

from cast import item_generator as ig_mod, npc_turn as npc_turn_mod
from cast.dice import roll_aggression
from cast.director_witness import (
    WITNESS_KIND_NPC_ATTACK,
    WITNESS_KIND_OBJECT_SMASH,
    WITNESS_MOOD_THREATENED,
    WitnessedAggression,
    build_npc_attack_witness,
    build_object_smash_witness,
    bump_guard_moods,
    is_guard_occupation,
)
from cast.schemas import item_response as item_resp, turn_outputs as to_mod
from knowledge.memory import MemoryManager
from llm.message import LLMResponse
from models.scene import SceneNPC
from tests.director_helpers import make_director, make_game_state, make_mock_actor, make_uuid, setup_npc

_GUARD_UUID = make_uuid("npc-1")
_TAILOR_UUID = make_uuid("npc-tailor")
_FORUM = make_uuid("forum")
_TAVERN = make_uuid("tavern")
_NEUTRAL = "neutral"


def _stub_item_generator(narration: str, delta: str) -> ig_mod.ItemGenerator:
    """Build a real ItemGenerator whose interact call returns fixed text."""
    gen = ig_mod.ItemGenerator(llm_client=MagicMock())
    gen._send_json = AsyncMock(  # type: ignore[method-assign]
        return_value=item_resp.ObjectInteractionResponse(narration=narration, delta=delta),
    )
    return gen


def _memory_manager_with_stub_llm(graph) -> MemoryManager:
    memory_llm = AsyncMock()
    memory_llm.send_message = AsyncMock(
        return_value=LLMResponse(body="unused summary", model="stub", usage={}),
    )
    return MemoryManager(graph=graph, llm_client=memory_llm)


def _seed_guard(gs) -> None:
    """Register a guard NPCCard for the default scene's npc-1 stub."""
    setup_npc(gs, _GUARD_UUID, name="Marcus", occupation="city guard")
    gs.knowledge_graph.register_actor_node(_GUARD_UUID, label="Marcus (city guard)")


def _seed_tailor(gs) -> None:
    """Add a second scene NPC with a non-guard occupation."""
    setup_npc(gs, _TAILOR_UUID, name="Lucia", occupation="tailor")
    gs.knowledge_graph.register_actor_node(_TAILOR_UUID, label="Lucia (tailor)")
    gs.current_scene.npcs_present.append(SceneNPC(role="tailor", uuid=_TAILOR_UUID))


@allure.epic("Combat & Action Resolution")
@allure.feature("Proximity witness broadcast")
class TestDirectorWitnessHelpers:
    @allure.story("Occupation classification")
    @allure.title("is_guard_occupation matches common watcher keywords case-insensitively")
    def test_is_guard_occupation_matches_variants(self):
        assert is_guard_occupation("guard")
        assert is_guard_occupation("city guard")
        assert is_guard_occupation("Night Watchman")
        assert is_guard_occupation("PRAETORIAN GUARD")
        assert is_guard_occupation("roman legionary")
        assert is_guard_occupation("sentry")

    @allure.story("Occupation classification")
    @allure.title("is_guard_occupation rejects civilian occupations and empty input")
    def test_is_guard_occupation_rejects_civilians(self):
        assert not is_guard_occupation("tailor")
        assert not is_guard_occupation("merchant")
        assert not is_guard_occupation("innkeeper")
        assert not is_guard_occupation("")
        assert not is_guard_occupation(None)

    @allure.story("Witness record")
    @allure.title("build_object_smash_witness combines the player action with the ItemGenerator delta")
    def test_build_object_smash_witness_combines_action_and_delta(self):
        event = build_object_smash_witness(
            target="shutter",
            delta_text="The front shutter hangs splintered and broken.",
            player_action="smash the shutter",
            location_id=_FORUM,
        )

        assert event.kind == WITNESS_KIND_OBJECT_SMASH
        assert event.target == "shutter"
        assert event.location_id == _FORUM
        assert "smash the shutter" in event.description
        assert "splintered" in event.description

    @allure.story("Witness record")
    @allure.title("build_npc_attack_witness records the NPC target and the player action (KER-33)")
    def test_build_npc_attack_witness_records_target_and_action(self):
        event = build_npc_attack_witness(
            target_name="Aulus",
            player_action="punch Aulus in the face",
            location_id=_FORUM,
        )

        assert event.kind == WITNESS_KIND_NPC_ATTACK
        assert event.target == "Aulus"
        assert event.location_id == _FORUM
        assert "punch Aulus in the face" in event.description
        assert "Aulus" in event.description

    @allure.story("Mood bump")
    @allure.title("bump_guard_moods flips neutral guards to threatened and returns the affected UUIDs")
    def test_bump_guard_moods_flips_neutral_guard(self):
        gs = make_game_state()
        _seed_guard(gs)

        bumped = bump_guard_moods(gs, [_GUARD_UUID])

        assert bumped == [_GUARD_UUID]
        assert gs.npcs[_GUARD_UUID].current_mood == WITNESS_MOOD_THREATENED

    @allure.story("Mood bump")
    @allure.title("bump_guard_moods leaves non-guard occupations at their current mood")
    def test_bump_guard_moods_skips_non_guard(self):
        gs = make_game_state()
        _seed_guard(gs)
        _seed_tailor(gs)

        bumped = bump_guard_moods(gs, [_GUARD_UUID, _TAILOR_UUID])

        assert bumped == [_GUARD_UUID]
        assert gs.npcs[_TAILOR_UUID].current_mood == _NEUTRAL

    @allure.story("Mood bump")
    @allure.title("bump_guard_moods does not downgrade an already-hostile guard")
    def test_bump_guard_moods_does_not_downgrade_hostile(self):
        gs = make_game_state()
        setup_npc(gs, _GUARD_UUID, name="Marcus", occupation="city guard", mood="hostile")

        bumped = bump_guard_moods(gs, [_GUARD_UUID])

        assert bumped == []
        assert gs.npcs[_GUARD_UUID].current_mood == "hostile"

    @allure.story("Aggression thresholds")
    @allure.title("threatened is a valid mood in AGGRESSION_THRESHOLDS so retaliation fires on subsequent turns")
    def test_threatened_mood_is_valid_aggression_mood(self):
        """Regression guard: the whole witness pipeline depends on
        ``WITNESS_MOOD_THREATENED`` being a key in ``AGGRESSION_THRESHOLDS``.
        If someone renames it to ``"alarmed"``, ``roll_aggression`` will
        silently return ``None`` and the retaliation check will drop the
        witness. Catch that drift here rather than in a flaky e2e run.
        """
        assert roll_aggression(WITNESS_MOOD_THREATENED) is not None


@allure.epic("Combat & Action Resolution")
@allure.feature("Proximity witness broadcast")
class TestInteractWithObjectsWitnessPublication:
    @allure.story("Witness publication")
    @allure.title("_interact_with_objects with is_aggressive=True publishes a WitnessedAggression to raw_outputs")
    @pytest.mark.asyncio
    async def test_aggressive_interact_publishes_witnessed_event(self):
        gs = make_game_state()
        _seed_guard(gs)
        director = make_director(game_state=gs)
        director._executor._item_generator = _stub_item_generator(
            "Wood splinters fly across the paving stones.",
            "The front shutter hangs splintered and broken.",
        )
        director._executor._memory_manager = _memory_manager_with_stub_llm(gs.knowledge_graph)
        raw_outputs = to_mod.TurnOutputs()

        await director._executor._interact_with_objects(
            targets=["shutter"],
            player_action="smash the shutter",
            is_aggressive=True,
            raw_outputs=raw_outputs,
        )

        assert len(raw_outputs.witnessed_events) == 1
        event = raw_outputs.witnessed_events[0]
        assert event.kind == WITNESS_KIND_OBJECT_SMASH
        assert event.target == "shutter"
        assert event.location_id == _FORUM
        assert "splintered" in event.description

    @allure.story("Mood bump")
    @allure.title("_interact_with_objects with is_aggressive=True flips a neutral guard to threatened")
    @pytest.mark.asyncio
    async def test_aggressive_interact_bumps_guard_mood(self):
        gs = make_game_state()
        _seed_guard(gs)
        _seed_tailor(gs)
        director = make_director(game_state=gs)
        director._executor._item_generator = _stub_item_generator(
            "Wood splinters fly across the paving stones.",
            "The front shutter hangs splintered and broken.",
        )
        director._executor._memory_manager = _memory_manager_with_stub_llm(gs.knowledge_graph)
        raw_outputs = to_mod.TurnOutputs()

        await director._executor._interact_with_objects(
            targets=["shutter"],
            player_action="smash the shutter",
            is_aggressive=True,
            raw_outputs=raw_outputs,
        )

        assert gs.npcs[_GUARD_UUID].current_mood == WITNESS_MOOD_THREATENED
        assert gs.npcs[_TAILOR_UUID].current_mood == _NEUTRAL

    @allure.story("Non-aggressive interact")
    @allure.title("_interact_with_objects with is_aggressive=False does not publish events nor bump moods")
    @pytest.mark.asyncio
    async def test_non_aggressive_does_not_publish_or_bump(self):
        gs = make_game_state()
        _seed_guard(gs)
        director = make_director(game_state=gs)
        director._executor._item_generator = _stub_item_generator(
            "You rattle the shutter; it does not yield.",
            "The shutter is slightly loose on its hinges.",
        )
        director._executor._memory_manager = _memory_manager_with_stub_llm(gs.knowledge_graph)
        raw_outputs = to_mod.TurnOutputs()

        await director._executor._interact_with_objects(
            targets=["shutter"],
            player_action="jiggle the shutter",
            is_aggressive=False,
            raw_outputs=raw_outputs,
        )

        assert raw_outputs.witnessed_events == []
        assert gs.npcs[_GUARD_UUID].current_mood == _NEUTRAL

    @allure.story("Empty delta")
    @allure.title("_interact_with_objects with an empty delta skips the witness broadcast even when aggressive")
    @pytest.mark.asyncio
    async def test_empty_delta_skips_witness_broadcast(self):
        gs = make_game_state()
        _seed_guard(gs)
        director = make_director(game_state=gs)
        director._executor._item_generator = _stub_item_generator(
            "Your fist glances off the stone wall.",
            "",
        )
        director._executor._memory_manager = _memory_manager_with_stub_llm(gs.knowledge_graph)
        raw_outputs = to_mod.TurnOutputs()

        await director._executor._interact_with_objects(
            targets=["wall"],
            player_action="punch the wall",
            is_aggressive=True,
            raw_outputs=raw_outputs,
        )

        assert raw_outputs.witnessed_events == []
        assert gs.npcs[_GUARD_UUID].current_mood == _NEUTRAL


@allure.epic("Combat & Action Resolution")
@allure.feature("Proximity witness broadcast")
class TestBuildTurnPromptIncidentClause:
    @allure.story("Incident clause")
    @allure.title("_build_turn_prompt appends the INCIDENT clause for a guard in the witnessed location")
    def test_build_turn_prompt_includes_incident_for_guard(self):
        gs = make_game_state()
        _seed_guard(gs)
        guard = gs.npcs[_GUARD_UUID]
        event = WitnessedAggression(
            kind=WITNESS_KIND_OBJECT_SMASH,
            target="shutter",
            location_id=_FORUM,
            description="smash the shutter. The front shutter hangs splintered and broken.",
        )

        prompt = npc_turn_mod._build_turn_prompt(
            guard,
            "smash the shutter",
            gs,
            [event],
        )

        assert "INCIDENT:" in prompt
        assert "shutter" in prompt
        assert "city guard" in prompt

    @allure.story("Incident clause")
    @allure.title("_build_turn_prompt omits the INCIDENT clause for a tailor in the same location")
    def test_build_turn_prompt_skips_incident_for_non_guard(self):
        gs = make_game_state()
        _seed_tailor(gs)
        tailor = gs.npcs[_TAILOR_UUID]
        event = WitnessedAggression(
            kind=WITNESS_KIND_OBJECT_SMASH,
            target="shutter",
            location_id=_FORUM,
            description="smash the shutter. The front shutter hangs splintered and broken.",
        )

        prompt = npc_turn_mod._build_turn_prompt(
            tailor,
            "smash the shutter",
            gs,
            [event],
        )

        assert "INCIDENT:" not in prompt

    @allure.story("Incident clause")
    @allure.title("_build_turn_prompt omits the INCIDENT clause when the event is pinned to a different location")
    def test_build_turn_prompt_skips_incident_for_other_location(self):
        gs = make_game_state()
        _seed_guard(gs)
        guard = gs.npcs[_GUARD_UUID]
        event = WitnessedAggression(
            kind=WITNESS_KIND_OBJECT_SMASH,
            target="shutter",
            location_id=_TAVERN,
            description="smash the shutter.",
        )

        prompt = npc_turn_mod._build_turn_prompt(
            guard,
            "smash the shutter",
            gs,
            [event],
        )

        assert "INCIDENT:" not in prompt

    @allure.story("Incident clause")
    @allure.title("_build_turn_prompt with no witnessed events produces the vanilla prompt")
    def test_build_turn_prompt_without_witnessed_events(self):
        gs = make_game_state()
        _seed_guard(gs)
        guard = gs.npcs[_GUARD_UUID]

        prompt = npc_turn_mod._build_turn_prompt(guard, "look around", gs, None)

        assert "INCIDENT:" not in prompt
        assert "Marcus's turn" in prompt


@allure.epic("Combat & Action Resolution")
@allure.feature("Proximity witness broadcast")
class TestShutterSmashRegression:
    @allure.story("Same-turn NPC reaction")
    @allure.title(
        "A full Director.act with aggressive INTERACT on the shutter surfaces a guard action on the same turn"
    )
    @pytest.mark.asyncio
    async def test_regression_shutter_smash_produces_npc_action_same_turn(self):
        """KER-18 primary regression — the Ancient Rome shutter scenario.

        Wire a full Director with a routing stub that classifies the
        action as aggressive INTERACT on the shutter, a scene containing
        a guard NPCCard, and a stubbed guard Actor that returns a raise-
        the-alarm JSON. Assert that the guard actor's autonomous-turn
        prompt contains the INCIDENT clause and the guard's mood has
        been flipped to ``threatened`` by the time the turn completes.
        """
        gs = make_game_state()
        _seed_guard(gs)
        route_response = {
            "action_type": "INTERACT",
            "is_aggressive": True,
            "targets": ["shutter"],
            "needs_clarification": False,
            "delegate_to": [],
        }
        director = make_director(game_state=gs, route_response=route_response)
        director._executor._item_generator = _stub_item_generator(
            "Wood splinters fly across the paving stones.",
            "The front shutter hangs splintered and broken.",
        )
        director._executor._memory_manager = _memory_manager_with_stub_llm(gs.knowledge_graph)
        guard_actor = make_mock_actor(
            '{"action": "The guard raises the alarm and rushes toward the player.", '
            '"type": "INTIMIDATE", "target": "player"}',
        )
        director._actors[_GUARD_UUID] = guard_actor

        narration = await director.act("smash the shutter")

        # Guard mood flipped to threatened by the witness broadcast.
        assert gs.npcs[_GUARD_UUID].current_mood == WITNESS_MOOD_THREATENED
        # The guard's Actor was invoked on this same turn for its
        # autonomous NPC turn — the prompt it received contains the
        # INCIDENT clause published by _interact_with_objects.
        assert guard_actor.execute.await_count == 1
        prompt = guard_actor.execute.await_args.kwargs.get("input_data")
        if prompt is None:
            prompt = guard_actor.execute.await_args.args[0]
        assert "INCIDENT:" in prompt
        assert "shutter" in prompt
        # Narrator returned a non-empty string (mocked fixture).
        assert narration
