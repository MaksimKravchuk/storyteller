"""Tests for procedural introduction detection.

Covers the three entry points of :mod:`cast.known_npcs`:

* :func:`resolve_revealed_uuids` — Signal A token → UUID resolution,
  scoped to the current scene.
* :func:`scan_player_text_for_known_uuids` — Signal B whole-word scan
  of raw player input against scene NPCs.
* :func:`mark_player_text_introductions` — the side-effecting wrapper
  invoked by the Director on every non-clarification turn.

Plus integration tests that drive the Director end-to-end and verify
``PlayerState.known_npcs`` is populated both via the Actor's
``[REVEALED:]`` tag *and* via the Signal B scanner after routing.
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import UUID

import allure
import pytest

from cast.known_npcs import (
    apply_revealed_reply,
    mark_player_text_introductions,
    resolve_revealed_uuids,
    scan_player_text_for_known_uuids,
)
from models.scene import Scene, SceneNPC
from tests._uuid_helpers import make_uuid
from tests.director_helpers import (
    actor_reply,
    make_director,
    make_game_state,
    make_mock_actor,
    setup_npc,
)

_NPC_A = make_uuid("npc-1")
_NPC_B = make_uuid("npc-2")
_NPC_OTHER_SCENE = make_uuid("npc-other")
_FORUM = make_uuid("forum")
_MARCUS = "Marcus"
_CASSIA = "Cassia"
_ACTION_TYPE = "action_type"
_TARGETS = "targets"
_NEEDS_CLARIFICATION = "needs_clarification"
_DELEGATE_TO = "delegate_to"


def _scene_with(*uuids: UUID) -> Scene:
    return Scene(
        location_id=_FORUM,
        description="The Forum.",
        npcs_present=[SceneNPC(role="npc", uuid=uid) for uid in uuids],
    )


@allure.epic("Memory & Persistence")
@allure.feature("Player knowledge")
class TestResolveRevealedUuids:
    @allure.story("Self token")
    @allure.title("The 'self' token resolves to the speaker's UUID when the speaker is in the current scene")
    def test_self_resolves_to_speaker(self):
        gs = make_game_state()
        setup_npc(gs, _NPC_A, name=_MARCUS, occupation="legionary")
        gs.current_scene = _scene_with(_NPC_A)

        uuids = resolve_revealed_uuids(["self"], _NPC_A, gs)

        assert uuids == {_NPC_A}

    @allure.story("Name token")
    @allure.title("A verbatim NPC name resolves case-insensitively to the matching scene NPC's UUID")
    def test_name_token_matches_case_insensitively(self):
        gs = make_game_state()
        setup_npc(gs, _NPC_A, name=_MARCUS, occupation="legionary")
        setup_npc(gs, _NPC_B, name=_CASSIA, occupation="innkeeper")
        gs.current_scene = _scene_with(_NPC_A, _NPC_B)

        uuids = resolve_revealed_uuids(["cassia"], _NPC_A, gs)

        assert uuids == {_NPC_B}

    @allure.story("Mixed tokens")
    @allure.title("Mixing 'self' with another scene NPC's name resolves both to UUIDs in a single call")
    def test_mixed_self_and_name(self):
        gs = make_game_state()
        setup_npc(gs, _NPC_A, name=_MARCUS, occupation="legionary")
        setup_npc(gs, _NPC_B, name=_CASSIA, occupation="innkeeper")
        gs.current_scene = _scene_with(_NPC_A, _NPC_B)

        uuids = resolve_revealed_uuids(["self", "Cassia"], _NPC_A, gs)

        assert uuids == {_NPC_A, _NPC_B}

    @allure.story("Scene isolation")
    @allure.title("An NPC with a matching name outside the current scene is NOT resolved (cross-scene leak guard)")
    def test_cross_scene_name_is_not_leaked(self):
        gs = make_game_state()
        setup_npc(gs, _NPC_A, name=_MARCUS, occupation="legionary")
        # Another "Cassia" exists in the world but is NOT in the current scene.
        setup_npc(gs, _NPC_OTHER_SCENE, name=_CASSIA, occupation="baker")
        gs.current_scene = _scene_with(_NPC_A)

        uuids = resolve_revealed_uuids([_CASSIA], _NPC_A, gs)

        assert uuids == set()

    @allure.story("Unknown token")
    @allure.title("A hallucinated name that matches no scene NPC is silently dropped")
    def test_unknown_name_dropped(self):
        gs = make_game_state()
        setup_npc(gs, _NPC_A, name=_MARCUS, occupation="legionary")
        gs.current_scene = _scene_with(_NPC_A)

        uuids = resolve_revealed_uuids(["Nobody"], _NPC_A, gs)

        assert uuids == set()


@allure.epic("Memory & Persistence")
@allure.feature("Player knowledge")
class TestScanPlayerText:
    @allure.story("Whole-word match")
    @allure.title("Typing an NPC's name in player input matches case-insensitively and returns that NPC's UUID")
    def test_whole_word_match(self):
        gs = make_game_state()
        setup_npc(gs, _NPC_A, name=_MARCUS, occupation="legionary")
        gs.current_scene = _scene_with(_NPC_A)

        uuids = scan_player_text_for_known_uuids("I walk up to marcus", gs)

        assert uuids == {_NPC_A}

    @allure.story("Word-boundary guard")
    @allure.title("An NPC named 'Art' must NOT match on the substring 'Art' inside 'Arthur'")
    def test_word_boundary_avoids_substring_false_match(self):
        gs = make_game_state()
        setup_npc(gs, _NPC_A, name="Art", occupation="cook")
        gs.current_scene = _scene_with(_NPC_A)

        uuids = scan_player_text_for_known_uuids("Arthur waves back", gs)

        assert uuids == set()

    @allure.story("Scene isolation")
    @allure.title("A name that exists elsewhere but is not in the current scene is not matched")
    def test_scene_isolation(self):
        gs = make_game_state()
        setup_npc(gs, _NPC_A, name=_MARCUS, occupation="legionary")
        setup_npc(gs, _NPC_OTHER_SCENE, name=_CASSIA, occupation="baker")
        gs.current_scene = _scene_with(_NPC_A)

        uuids = scan_player_text_for_known_uuids("I ask Cassia about the road", gs)

        assert uuids == set()

    @allure.story("Cyrillic names")
    @allure.title("A Cyrillic NPC name is matched via Unicode-aware word boundaries")
    def test_cyrillic_name_matches(self):
        gs = make_game_state()
        setup_npc(gs, _NPC_A, name="Луций", occupation="страж")
        gs.current_scene = _scene_with(_NPC_A)

        uuids = scan_player_text_for_known_uuids("иду к Луций", gs)

        assert uuids == {_NPC_A}

    @allure.story("Uninitialised SceneNPC")
    @allure.title("An uninitialised SceneNPC stub without a UUID contributes nothing to the scan")
    def test_uninitialised_stub_ignored(self):
        gs = make_game_state()
        setup_npc(gs, _NPC_A, name=_MARCUS, occupation="legionary")
        gs.current_scene = Scene(
            location_id=_FORUM,
            description="The Forum.",
            npcs_present=[SceneNPC(role="npc", uuid=_NPC_A), SceneNPC(role="beggar")],
        )

        uuids = scan_player_text_for_known_uuids("I look at the beggar", gs)

        assert uuids == set()

    @allure.story("No scene")
    @allure.title("A game with no current scene returns an empty match set")
    def test_no_scene_returns_empty(self):
        gs = make_game_state()
        gs.current_scene = None

        uuids = scan_player_text_for_known_uuids("Marcus!", gs)

        assert uuids == set()


@allure.epic("Memory & Persistence")
@allure.feature("Player knowledge")
class TestMarkPlayerTextIntroductions:
    @allure.story("Side-effect wrapper")
    @allure.title("mark_player_text_introductions adds matched UUIDs to PlayerState.known_npcs in place")
    def test_marks_player_known_npcs(self):
        gs = make_game_state()
        setup_npc(gs, _NPC_A, name=_MARCUS, occupation="legionary")
        gs.current_scene = _scene_with(_NPC_A)
        assert _NPC_A not in gs.player.known_npcs

        newly = mark_player_text_introductions("hail Marcus!", gs)

        assert newly == {_NPC_A}
        assert _NPC_A in gs.player.known_npcs

    @allure.story("Side-effect wrapper")
    @allure.title("Repeated mentions of an already-known NPC return an empty newly-added set")
    def test_repeat_mention_returns_no_new_additions(self):
        gs = make_game_state()
        setup_npc(gs, _NPC_A, name=_MARCUS, occupation="legionary")
        gs.current_scene = _scene_with(_NPC_A)
        gs.player.known_npcs.add(_NPC_A)

        newly = mark_player_text_introductions("hail Marcus again", gs)

        assert newly == set()
        assert _NPC_A in gs.player.known_npcs


@allure.epic("Memory & Persistence")
@allure.feature("Player knowledge")
class TestDirectorAppliesSignals:
    """End-to-end: Director.act wires both signals into ``known_npcs``."""

    @allure.story("Signal B via Director")
    @allure.title("Typing an NPC's name adds that NPC's UUID to PlayerState.known_npcs (Signal B)")
    @pytest.mark.asyncio
    async def test_director_marks_player_known_via_text_scan(self):
        gs = make_game_state()
        setup_npc(gs, _NPC_A, name=_MARCUS, occupation="legionary")
        gs.current_scene = _scene_with(_NPC_A)

        director = make_director(
            game_state=gs,
            route_response={
                _ACTION_TYPE: "TALK",
                _TARGETS: [_MARCUS],
                _NEEDS_CLARIFICATION: False,
                _DELEGATE_TO: ["actor", "narrator"],
            },
        )
        director._actors[_NPC_A] = make_mock_actor("Ave.")

        await director.act("I greet Marcus")

        assert _NPC_A in gs.player.known_npcs

    @allure.story("Signal A via Director")
    @allure.title("An Actor reply with [REVEALED: self] adds the speaker's UUID to PlayerState.known_npcs")
    @pytest.mark.asyncio
    async def test_director_marks_player_known_via_revealed_self(self):
        gs = make_game_state()
        setup_npc(gs, _NPC_A, name=_MARCUS, occupation="legionary")
        gs.current_scene = _scene_with(_NPC_A)

        director = make_director(
            game_state=gs,
            route_response={
                _ACTION_TYPE: "TALK",
                _TARGETS: [_MARCUS],
                _NEEDS_CLARIFICATION: False,
                _DELEGATE_TO: ["actor", "narrator"],
            },
        )
        mock_actor = AsyncMock()
        mock_actor.execute = AsyncMock(
            return_value=actor_reply(text="I am Marcus.", revealed_names=["self"]),
        )
        director._actors[_NPC_A] = mock_actor

        await director.act("who are you, soldier?")

        assert _NPC_A in gs.player.known_npcs

    @allure.story("Signal A via Director")
    @allure.title("A revealed name pointing at another scene NPC adds that NPC's UUID as well")
    @pytest.mark.asyncio
    async def test_director_marks_other_npc_via_revealed_name(self):
        gs = make_game_state()
        setup_npc(gs, _NPC_A, name=_MARCUS, occupation="legionary")
        setup_npc(gs, _NPC_B, name=_CASSIA, occupation="innkeeper")
        gs.current_scene = _scene_with(_NPC_A, _NPC_B)

        director = make_director(
            game_state=gs,
            route_response={
                _ACTION_TYPE: "TALK",
                _TARGETS: [_MARCUS],
                _NEEDS_CLARIFICATION: False,
                _DELEGATE_TO: ["actor", "narrator"],
            },
        )
        marcus_actor = AsyncMock()
        marcus_actor.execute = AsyncMock(
            return_value=actor_reply(
                text="I am Marcus — that is Cassia, the innkeeper.",
                revealed_names=["self", "Cassia"],
            ),
        )
        director._actors[_NPC_A] = marcus_actor
        director._actors[_NPC_B] = make_mock_actor("")

        await director.act("who are you and who is she?")

        assert {_NPC_A, _NPC_B} <= gs.player.known_npcs

    @allure.story("Signal B via Director")
    @allure.title("A clarification turn does not add any scene-NPC UUIDs to known_npcs (Signal B is skipped)")
    @pytest.mark.asyncio
    async def test_clarification_turn_skips_signal_b(self):
        gs = make_game_state()
        setup_npc(gs, _NPC_A, name=_MARCUS, occupation="legionary")
        gs.current_scene = _scene_with(_NPC_A)

        director = make_director(
            game_state=gs,
            route_response={
                _NEEDS_CLARIFICATION: True,
                "clarification_question": "Which Marcus?",
            },
        )

        await director.act("I walk up to Marcus")

        assert gs.player.known_npcs == set()


@allure.epic("Memory & Persistence")
@allure.feature("Player knowledge")
class TestApplyRevealedReply:
    @allure.story("Signal A helper")
    @allure.title("apply_revealed_reply is a no-op when the reply carries no revealed_names")
    def test_empty_revealed_names_is_noop(self):
        gs = make_game_state()
        setup_npc(gs, _NPC_A, name=_MARCUS, occupation="legionary")
        gs.current_scene = _scene_with(_NPC_A)

        apply_revealed_reply(actor_reply(text="Hello."), _NPC_A, gs)

        assert gs.player.known_npcs == set()

    @allure.story("Signal A helper")
    @allure.title("apply_revealed_reply unions resolved UUIDs into PlayerState.known_npcs")
    def test_resolved_uuids_unioned_into_known_npcs(self):
        gs = make_game_state()
        setup_npc(gs, _NPC_A, name=_MARCUS, occupation="legionary")
        gs.current_scene = _scene_with(_NPC_A)

        apply_revealed_reply(
            actor_reply(text="I am Marcus.", revealed_names=["self"]),
            _NPC_A,
            gs,
        )

        assert _NPC_A in gs.player.known_npcs


@allure.epic("Combat & Action Resolution")
@allure.feature("NPC retaliation")
class TestRetaliationAppliesRevealedNames:
    """The retaliation path also consumes ``[REVEALED:]`` tokens.

    Guards against a silent regression that would drop the call to
    :func:`apply_revealed_reply` from ``_execute_retaliation`` — the
    same Actor helper that dialogue uses.
    """

    @allure.story("Retaliation introduces speaker")
    @allure.title("A retaliating NPC whose reply carries [REVEALED: self] adds its UUID to PlayerState.known_npcs")
    @pytest.mark.asyncio
    async def test_retaliation_reveal_populates_known_npcs(self):
        from cast.director_retaliation import RetaliationHandler
        from tests.test_director_retaliation import (
            _fixed_combat,
            _make_aggression_stub,
            _run_patched,
        )

        gs = make_game_state()
        npc = setup_npc(gs, _NPC_A, name=_MARCUS, occupation="legionary", mood="hostile")
        npc.hostility_level = 5
        mock_actor = AsyncMock()
        mock_actor.execute = AsyncMock(
            return_value=actor_reply(text="I am Marcus — stand down!", revealed_names=["self"]),
        )
        handler = RetaliationHandler(gs, {_NPC_A: mock_actor})

        entries = await _run_patched(
            _make_aggression_stub(True),
            handler.check_retaliation({_NPC_A: "neutral"}),
            combat_replacement=_fixed_combat,
        )

        assert len(entries) == 1
        assert _NPC_A in gs.player.known_npcs
