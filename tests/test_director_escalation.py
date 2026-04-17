"""Director-side regression tests for NPC conflict escalation.

- The Director mechanically bumps ``hostility_level`` on aggressive turns
  so the Actor prompt no longer depends on the LLM remembering to emit
  ``[MOOD:]``.
- Hostility history persists onto the NPCCard (FIFO, cap 3).
- Once an NPC's hostility crosses :data:`cast.hostility.RETALIATION_THRESHOLD`,
  the retaliation phase is *forced* to roll even when the dialogue call
  already resolved a defensive combat contest — so repeat assaults get an
  offensive counter-attack on the same turn.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import allure
import pytest

from cast import director_dialogue, director_hostility, director_retaliation, hostility
from cast.dice import AggressionRoll, CombatOutcome, CombatRoll
from models.npc_card import NPCCard
from models.scene import SceneNPC
from tests.director_helpers import make_director, make_game_state, make_mock_agent, setup_npc

_NPC_A = "npc-1"
_GUARD = "guard"
_ATTACK_ROLL = 15

_IDLE_JSON = '{"action": "guard watches", "type": "IDLE", "target": null}'


def _aggressive_route():
    return {
        "action_type": "INTERACT",
        "is_aggressive": True,
        "targets": (_GUARD,),
        "needs_clarification": False,
        "delegate_to": ["actor", "narrator"],
    }


def _force_attack(mood: str, _rng: Any = None) -> AggressionRoll:
    return AggressionRoll(
        will_attack=True,
        roll=_ATTACK_ROLL,
        threshold=5,
        mood=mood,
    )


def _fixed_combat(combat_skill_val: int, _rng: Any = None) -> CombatRoll:
    return CombatRoll(
        outcome=CombatOutcome.TARGET_DOMINATES,
        npc_roll=_ATTACK_ROLL,
        player_roll=5,
        npc_bonus=combat_skill_val,
    )


@pytest.fixture
def force_attack_rolls(monkeypatch):
    """Pin aggression + combat rolls so the retaliation phase is deterministic."""
    monkeypatch.setattr(director_retaliation, "roll_aggression", _force_attack)
    monkeypatch.setattr(director_retaliation, "roll_combat", _fixed_combat)
    monkeypatch.setattr(director_dialogue, "roll_combat", _fixed_combat, raising=False)


def _make_actor_returning(*responses: str) -> AsyncMock:
    """Build a mock actor whose execute() cycles through the given responses."""
    mock = AsyncMock()
    mock.act = AsyncMock(return_value=responses[0])
    mock.execute = AsyncMock(side_effect=list(responses))
    return mock


def _register_guard(gs, *, hostility_level: int = 0, mood: str = "neutral") -> NPCCard:
    npc = setup_npc(gs, _NPC_A, name="Guard", occupation="city guard", mood=mood)
    npc.hostility_level = hostility_level
    return npc


def _retaliation_input_of(actor: AsyncMock, call_index: int) -> str:
    """Pull the ``input_data`` argument of one recorded execute() call."""
    call = actor.execute.call_args_list[call_index]
    return call.kwargs.get("input_data") or ""


@allure.epic("NPC behavior")
@allure.feature("Hostility escalation")
class TestDirectorBumpsHostility:
    @allure.story("Pre-dialogue bump")
    @allure.title("Aggressive turn bumps the target NPC's hostility_level and raises current_mood deterministically")
    @pytest.mark.asyncio
    async def test_aggressive_turn_bumps_hostility(self, force_attack_rolls):
        gs = make_game_state()
        npc = _register_guard(gs)
        director = make_director(game_state=gs, route_response=_aggressive_route())
        director._actors[_NPC_A] = _make_actor_returning("*stands firm*", _IDLE_JSON)

        await director.act("punch the guard")

        assert npc.hostility_level == 2
        assert npc.current_mood == "irritated"
        assert len(npc.recent_hostile_actions) == 1
        assert npc.recent_hostile_actions[0]["action"] == "punch the guard"
        assert npc.recent_hostile_actions[0]["severity"] == hostility.SEVERITY_HIGH

    @allure.story("Pre-dialogue bump")
    @allure.title("Non-aggressive turn leaves hostility_level at zero")
    @pytest.mark.asyncio
    async def test_non_aggressive_turn_does_not_bump(self):
        gs = make_game_state()
        npc = _register_guard(gs)
        director = make_director(
            game_state=gs,
            route_response={
                "action_type": "TALK",
                "targets": (_GUARD,),
                "is_aggressive": False,
                "needs_clarification": False,
                "delegate_to": ["actor", "narrator"],
            },
        )
        director._actors[_NPC_A] = _make_actor_returning("Hello traveler.", _IDLE_JSON)

        await director.act("greet the guard")

        assert npc.hostility_level == 0
        assert npc.recent_hostile_actions == []


@allure.epic("NPC behavior")
@allure.feature("Hostility escalation")
class TestForcedRetaliation:
    @allure.story("Same-turn counter-attack")
    @allure.title("An NPC whose hostility has crossed the retaliation threshold gets a forced counter-attack call")
    @pytest.mark.asyncio
    async def test_high_hostility_forces_retaliation(self, force_attack_rolls):
        gs = make_game_state()
        # Pre-seed: the NPC has been assaulted before, hostility is past the threshold.
        _register_guard(gs, hostility_level=hostility.RETALIATION_THRESHOLD, mood="threatened")
        director = make_director(game_state=gs, route_response=_aggressive_route())
        director._actors[_NPC_A] = _make_actor_returning(
            "*braces*",
            "*lunges forward*",
            _IDLE_JSON,
        )

        await director.act("punch the guard")

        actor = director._actors[_NPC_A]
        # Three calls: dialogue (defensive) + retaliation (offensive) + NPC turn.
        assert actor.execute.call_count == 3
        assert "retaliates against the player" in _retaliation_input_of(actor, 1)

    @allure.story("Same-turn counter-attack")
    @allure.title("Forced retaliation still fires when the dialogue LLM tries to downgrade mood to [MOOD: calm]")
    @pytest.mark.asyncio
    async def test_forced_retaliation_survives_llm_mood_downgrade(self, force_attack_rolls):
        """Regression: without the Actor-side ``apply_llm_mood_update`` guard,
        an LLM emitting ``[MOOD: calm]`` after the Director bumped the guard to
        ``threatened`` would reset ``current_mood`` to ``calm``, making
        ``roll_aggression`` return ``None`` — no counter-attack would roll
        even though ``force_uuids`` listed the NPC.
        """
        gs = make_game_state()
        npc = _register_guard(gs, hostility_level=hostility.RETALIATION_THRESHOLD, mood="threatened")
        director = make_director(game_state=gs, route_response=_aggressive_route())
        # Dialogue response explicitly tries to *downgrade* the mood.
        director._actors[_NPC_A] = _make_actor_returning(
            "*braces*\n[MOOD: calm]",
            "*lunges forward*",
            _IDLE_JSON,
        )

        await director.act("punch the guard")

        actor = director._actors[_NPC_A]
        assert actor.execute.call_count == 3, "retaliation must still fire despite [MOOD: calm]"
        # Director bumps level 3→5 before dialogue, so the floor climbs to "angry";
        # the LLM's [MOOD: calm] is below that floor and is rejected.
        assert npc.current_mood == "angry", "mechanical floor must hold against LLM downgrade"

    @allure.story("Same-turn counter-attack")
    @allure.title(
        "A first-assault NPC below the hostility threshold keeps the single dialogue call (no double-narration)"
    )
    @pytest.mark.asyncio
    async def test_below_threshold_still_skipped(self, force_attack_rolls):
        gs = make_game_state()
        _register_guard(gs)
        director = make_director(game_state=gs, route_response=_aggressive_route())
        director._actors[_NPC_A] = _make_actor_returning("*stands firm*", _IDLE_JSON)

        await director.act("punch the guard")

        actor = director._actors[_NPC_A]
        # A single aggressive turn bumps level to 2 (below RETALIATION_THRESHOLD=3),
        # so we keep the original contract: dialogue + NPC turn, no retaliation call.
        assert actor.execute.call_count == 2


@allure.epic("NPC behavior")
@allure.feature("Hostility escalation")
class TestMultiTargetAndRoleResolution:
    @allure.story("Pre-dialogue bump")
    @allure.title("Multi-target aggressive turn bumps hostility independently for every named NPC")
    @pytest.mark.asyncio
    async def test_multi_target_bumps_each_npc(self, force_attack_rolls):
        gs = make_game_state()
        guard_a = setup_npc(gs, "uuid-a", name="Aulus", occupation="city guard")
        guard_b = setup_npc(gs, "uuid-b", name="Bassus", occupation="city guard")
        gs.current_scene.npcs_present.append(SceneNPC(role="city guard", uuid="uuid-b"))

        force_uuids = director_hostility.apply_aggressive_turn(
            gs,
            ["Aulus", "Bassus"],
            "swing at both guards",
        )

        assert guard_a.hostility_level == 2
        assert guard_b.hostility_level == 2
        # Both below RETALIATION_THRESHOLD after a single bump.
        assert force_uuids == set()
        assert guard_a.recent_hostile_actions[0]["action"] == "swing at both guards"
        assert guard_b.recent_hostile_actions[0]["action"] == "swing at both guards"

    @allure.story("Pre-dialogue bump")
    @allure.title("Role-only targets (e.g. 'sentry') resolve through the scene role and still get bumped")
    @pytest.mark.asyncio
    async def test_role_only_target_is_bumped(self):
        gs = make_game_state()
        # NPC with distinct name vs. scene role — e.g. "Quintus" occupying a "sentry" post.
        gs.current_scene.npcs_present.clear()
        gs.current_scene.npcs_present.append(SceneNPC(role="sentry", uuid="uuid-q"))
        quintus = setup_npc(gs, "uuid-q", name="Quintus", occupation="sentry")

        director_hostility.apply_aggressive_turn(gs, ["sentry"], "punch the sentry")

        assert quintus.hostility_level == 2
        assert quintus.recent_hostile_actions[0]["action"] == "punch the sentry"


@allure.epic("NPC behavior")
@allure.feature("Hostility escalation")
class TestRetaliationHandlerSkipForceInteraction:
    @allure.story("Handler contract")
    @allure.title("When a UUID appears in both skip_uuids and force_uuids, skip wins")
    @pytest.mark.asyncio
    async def test_skip_beats_force_when_both_supplied(self, force_attack_rolls):
        gs = make_game_state()
        target = setup_npc(gs, _NPC_A, name="Guard", occupation="city guard", mood="threatened")
        target.hostility_level = 4
        actor = make_mock_agent("*should not be called*")
        handler = director_retaliation.RetaliationHandler(gs, {_NPC_A: actor})

        entries = await handler.check_retaliation(
            mood_snapshot={_NPC_A: "neutral"},
            skip_uuids={_NPC_A},
            force_uuids={_NPC_A},
        )

        assert entries == []
        assert actor.execute.call_count == 0


@allure.epic("NPC behavior")
@allure.feature("Hostility escalation")
class TestHostilityHistory:
    @allure.story("FIFO history")
    @allure.title("Consecutive aggressive turns accumulate recent_hostile_actions in FIFO order, cap 3")
    @pytest.mark.asyncio
    async def test_history_accumulates_across_turns(self, force_attack_rolls):
        gs = make_game_state()
        npc = _register_guard(gs)
        director = make_director(game_state=gs, route_response=_aggressive_route())
        # Turn 1: below threshold → 2 execute calls (dialogue + NPC turn).
        # Turns 2-4: hostility ≥ 3 → 3 execute calls each (dialogue + retaliation + NPC turn).
        # Total = 2 + 3 + 3 + 3 = 11 responses.
        director._actors[_NPC_A] = _make_actor_returning(
            "*blocks*",
            _IDLE_JSON,
            "*blocks*",
            "*lunges*",
            _IDLE_JSON,
            "*blocks*",
            "*lunges*",
            _IDLE_JSON,
            "*blocks*",
            "*lunges*",
            _IDLE_JSON,
        )

        await director.act("shove the guard")
        await director.act("punch the guard")
        await director.act("kick the guard")
        await director.act("stab the guard")

        assert len(npc.recent_hostile_actions) == 3
        assert npc.recent_hostile_actions[0]["action"] == "punch the guard"
        assert npc.recent_hostile_actions[-1]["action"] == "stab the guard"
        assert npc.hostility_level == 8
        # After four high-severity bumps the mood floor is at "hostile" (level 7-8).
        assert npc.current_mood == "hostile"
