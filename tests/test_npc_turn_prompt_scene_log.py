"""Consumer-side tests: scene action log reaches the NPC's turn prompt body.

Without these tests the supplier→consumer wiring (CLAUDE.md §Testing) is
unproven — a future refactor of the entry render format would silently
break what the LLM actually sees on the wire.
"""

from __future__ import annotations

import allure

from cast import npc_turn as npc_turn_mod
from cast import scene_log as scene_log_mod
from cast.player_context import PlayerUtterance
from knowledge.graph import KnowledgeGraph
from models.game_state import GameState
from models.npc_card import NPCCard
from models.scene import Scene, SceneNPC
from models.scene_action_log import ActorKind, SceneActionEntry
from models.setting import Setting
from tests._uuid_helpers import make_uuid

_NPC_UUID_A = make_uuid("npc-a")
_NPC_UUID_B = make_uuid("npc-b")


def _make_gs() -> GameState:
    return GameState(
        setting=Setting(name="Rome", time_period="1 AD", region="Italy", summary=""),
        knowledge_graph=KnowledgeGraph(),
    )


def _make_npc(uuid, name: str) -> NPCCard:
    npc = NPCCard(name=name, occupation="test")
    npc.uuid = uuid
    return npc


def _seed_scene(gs: GameState, *npcs: NPCCard) -> None:
    scene_npcs = [SceneNPC(role="npc", uuid=present_npc.uuid) for present_npc in npcs]
    for card in npcs:
        gs.npcs[card.uuid] = card
    gs.current_scene = Scene(
        location_id=make_uuid("forum"),
        description="The bustling Forum.",
        npcs_present=scene_npcs,
    )


@allure.epic("NPC short-term memory")
@allure.feature("Scene log in NPC prompt")
class TestPromptContainsSceneLog:
    @allure.story("Prompt rendering")
    @allure.title("Each scene_action_log entry's description and actor name appear verbatim in the NPC prompt")
    def test_entries_appear_in_prompt_body(self):
        gs = _make_gs()
        marcus = _make_npc(_NPC_UUID_A, "Marcus")
        livia = _make_npc(_NPC_UUID_B, "Livia")
        _seed_scene(gs, marcus, livia)

        scene_log_mod.append_player_action(gs, "TALK", "I demand the silver back.")
        gs.scene_action_log.append(
            SceneActionEntry(
                actor_kind=ActorKind.NPC,
                actor_uuid=livia.uuid,
                actor_name="Livia",
                action_type="TALK",
                description="Livia laughs in your face.",
                game_clock=1.0,
            ),
        )
        scene_log_mod.append_event(
            gs,
            scene_log_mod.WitnessedEvent(
                event_type="WITNESS",
                description="A bystander shouts for the guards.",
                witness_ids=[marcus.uuid, livia.uuid],
                already_persisted=True,
            ),
        )

        prompt = npc_turn_mod._build_turn_prompt(marcus, "Player tries to barter.", gs)

        assert "THIS SCENE SO FAR:" in prompt
        assert "I demand the silver back." in prompt
        assert "Livia laughs in your face." in prompt
        assert "A bystander shouts for the guards." in prompt
        assert "Livia" in prompt

    @allure.story("Prompt rendering")
    @allure.title("Empty scene_action_log omits the SCENE SO FAR clause entirely")
    def test_empty_log_omits_clause(self):
        gs = _make_gs()
        marcus = _make_npc(_NPC_UUID_A, "Marcus")
        _seed_scene(gs, marcus)

        prompt = npc_turn_mod._build_turn_prompt(marcus, "Player waits.", gs)
        assert "THIS SCENE SO FAR:" not in prompt


@allure.epic("NPC short-term memory")
@allure.feature("Scene log in NPC prompt")
class TestPromptLiteraryPlayerEntries:
    @allure.story("Literary phrasing")
    @allure.title("Player scene-log entries render via PlayerUtterance when player.appearance is set")
    def test_player_entries_render_literarily(self):
        gs = _make_gs()
        gs.player.appearance = "190 cm Slav in dark furs"
        marcus = _make_npc(_NPC_UUID_A, "Marcus")
        _seed_scene(gs, marcus)

        scene_log_mod.append_player_action(gs, "TALK", "I demand the silver.")
        gs.scene_action_log.append(
            SceneActionEntry(
                actor_kind=ActorKind.NPC,
                actor_uuid=marcus.uuid,
                actor_name="Marcus",
                action_type="TALK",
                description="Marcus refuses.",
                game_clock=1.0,
            ),
        )

        utterance = PlayerUtterance(
            appearance="190 cm Slav in dark furs",
            action_type="ATTACK",
            text="I draw my sword.",
        )
        prompt = npc_turn_mod._build_turn_prompt(marcus, utterance, gs)

        # Player scene-log entry uses PlayerUtterance.
        assert 'The 190 cm Slav in dark furs says: "I demand the silver."' in prompt
        # NPC scene-log entry stays in the bare form.
        assert "Marcus: Marcus refuses." in prompt
        # Per-turn cue uses PlayerUtterance with the current action_type.
        assert "Recent events: The 190 cm Slav in dark furs attacks: I draw my sword." in prompt

    @allure.story("Literary phrasing")
    @allure.title("Without an appearance, player entries fall back to the bare 'Player: ...' form")
    def test_unremarkable_appearance_falls_back_to_bare_form(self):
        gs = _make_gs()
        # gs.player.appearance defaults to "" → format_player_appearance returns "unremarkable".
        marcus = _make_npc(_NPC_UUID_A, "Marcus")
        _seed_scene(gs, marcus)

        scene_log_mod.append_player_action(gs, "TALK", "I greet the merchant.")

        utterance = PlayerUtterance(appearance="", action_type="EXPLORE", text="I look around.")
        prompt = npc_turn_mod._build_turn_prompt(marcus, utterance, gs)

        # No "A <descriptor> man" prefix; bare Player form.
        assert "A 190 cm" not in prompt
        assert 'Player says: "I greet the merchant."' in prompt
        assert "Recent events: Player looks around, doing: I look around." in prompt


@allure.epic("NPC short-term memory")
@allure.feature("Scene log in NPC prompt")
class TestPromptCapsLogSize:
    @allure.story("Prompt rendering")
    @allure.title("Long scene logs are capped to the most recent N entries; earliest are dropped")
    def test_long_log_keeps_only_recent_tail(self):
        gs = _make_gs()
        marcus = _make_npc(_NPC_UUID_A, "Marcus")
        _seed_scene(gs, marcus)

        for idx in range(100):
            gs.scene_action_log.append(
                SceneActionEntry(
                    actor_kind=ActorKind.PLAYER,
                    actor_uuid=gs.player.uuid,
                    actor_name="Player",
                    action_type="TALK",
                    description="player utterance number {0}".format(idx),
                    game_clock=float(idx),
                ),
            )

        prompt = npc_turn_mod._build_turn_prompt(marcus, "Player keeps talking.", gs)

        assert "player utterance number 99" in prompt
        assert "player utterance number 0" not in prompt
        # The first ~75 entries must have been dropped from the render.
        assert "player utterance number 50" not in prompt

    @allure.story("Prompt rendering")
    @allure.title("Per-entry description is truncated so a runaway entry cannot blow up the prompt")
    def test_long_description_is_truncated(self):
        gs = _make_gs()
        marcus = _make_npc(_NPC_UUID_A, "Marcus")
        _seed_scene(gs, marcus)

        runaway = "x" * 5000
        gs.scene_action_log.append(
            SceneActionEntry(
                actor_kind=ActorKind.PLAYER,
                actor_uuid=gs.player.uuid,
                actor_name="Player",
                action_type="TALK",
                description=runaway,
                game_clock=1.0,
            ),
        )

        prompt = npc_turn_mod._build_turn_prompt(marcus, "Player keeps talking.", gs)
        # Only the truncated tail should reach the prompt body.
        assert "x" * 5000 not in prompt
        assert "x" * 200 in prompt
