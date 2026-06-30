"""Tests for Director context formatting — NPC labels with physical status."""

from __future__ import annotations

import allure

from cast.director_context import ContextFormatter, format_npcs_present
from cast.player_context import format_player_appearance, format_player_inventory
from knowledge.graph import KnowledgeGraph
from models.game_state import GameState, PlayerState
from models.npc_card import NPCCard
from models.scene import Scene, SceneNPC
from models.scene_action_log import ActorKind, SceneActionEntry
from models.setting import Setting
from models.visible_entity import VisibleEntity
from tests._uuid_helpers import make_uuid

_GUARD_NAME = "Guard"
_GUARD = "guard"
_LOC = make_uuid("loc1")


class _CapturingPerformer:
    """Minimal stub that records ``set_context`` kwargs for assertions."""

    def __init__(self) -> None:
        self.kwargs: dict[str, str] = {}

    def set_context(self, **kwargs: str) -> None:
        self.kwargs.update(kwargs)


def _make_game_state_with_npcs(npc_list: list[NPCCard]) -> GameState:
    gs = GameState(
        setting=Setting(
            name="Rome",
            time_period="1 AD",
            region="Italy",
            summary="",
            technologies=["aqueducts", "wax tablets"],
            social_structure="senators, equites, plebs, freedmen, and enslaved people",
        ),
        knowledge_graph=KnowledgeGraph(),
    )
    for npc in npc_list:
        gs.npcs[npc.uuid] = npc
    return gs


@allure.epic("NPC Interaction")
@allure.feature("Director context formatting")
@allure.story("NPC label formatting")
class TestFormatNpcsPresent:
    @allure.title("A healthy NPC with no appearance renders as a bare bullet line")
    def test_healthy_npc_shows_name_only(self):
        npc = NPCCard(name=_GUARD_NAME, occupation=_GUARD, physical_status="healthy")
        gs = _make_game_state_with_npcs([npc])
        scene = Scene(
            location_id=_LOC,
            npcs_present=[SceneNPC(role=_GUARD, uuid=npc.uuid)],
        )
        formatted = format_npcs_present(scene, gs)
        assert formatted == "- {0}".format(_GUARD_NAME)

    @allure.title("A wounded NPC renders the physical status suffix in its bullet line")
    def test_wounded_npc_shows_status(self):
        npc = NPCCard(name=_GUARD_NAME, occupation=_GUARD, physical_status="wounded left arm")
        gs = _make_game_state_with_npcs([npc])
        scene = Scene(
            location_id=_LOC,
            npcs_present=[SceneNPC(role=_GUARD, uuid=npc.uuid)],
        )
        formatted = format_npcs_present(scene, gs)
        assert formatted == "- {0} (wounded left arm)".format(_GUARD_NAME)

    @allure.title("Each NPC renders on its own bullet line so the Director can disambiguate them")
    def test_mixed_healthy_and_wounded(self):
        guard = NPCCard(name=_GUARD_NAME, occupation=_GUARD, physical_status="barely standing")
        merchant = NPCCard(name="Merchant", occupation="merchant", physical_status="healthy")
        gs = _make_game_state_with_npcs([guard, merchant])
        scene = Scene(
            location_id=_LOC,
            npcs_present=[
                SceneNPC(role=_GUARD, uuid=guard.uuid),
                SceneNPC(role="merchant", uuid=merchant.uuid),
            ],
        )
        formatted = format_npcs_present(scene, gs)
        lines = formatted.split("\n")
        assert lines == [
            "- {0} (barely standing)".format(_GUARD_NAME),
            "- Merchant",
        ]

    @allure.title("Appearance is appended after an em-dash so player references like 'guy in helmet' resolve")
    def test_appearance_included_in_line(self):
        guard = NPCCard(
            name="Crassus",
            occupation=_GUARD,
            physical_status="healthy",
            appearance="Broad-shouldered, segmented armour, helmet, gladius at the hip",
        )
        beggar = NPCCard(
            name="Tertius",
            occupation="beggar",
            physical_status="healthy",
            appearance="Gaunt, ragged tunic, dirty cloak",
        )
        gs = _make_game_state_with_npcs([guard, beggar])
        scene = Scene(
            location_id=_LOC,
            npcs_present=[
                SceneNPC(role=_GUARD, uuid=guard.uuid),
                SceneNPC(role="beggar", uuid=beggar.uuid),
            ],
        )
        formatted = format_npcs_present(scene, gs)
        assert "Crassus — Broad-shouldered, segmented armour, helmet, gladius at the hip" in formatted
        assert "Tertius — Gaunt, ragged tunic, dirty cloak" in formatted

    @allure.title("A wounded NPC with appearance renders as '- Name (status) — appearance'")
    def test_wounded_with_appearance(self):
        npc = NPCCard(
            name="Crassus",
            occupation=_GUARD,
            physical_status="wounded left arm",
            appearance="Broad-shouldered, segmented armour, helmet",
        )
        gs = _make_game_state_with_npcs([npc])
        scene = Scene(
            location_id=_LOC,
            npcs_present=[SceneNPC(role=_GUARD, uuid=npc.uuid)],
        )
        formatted = format_npcs_present(scene, gs)
        assert formatted == "- Crassus (wounded left arm) — Broad-shouldered, segmented armour, helmet"

    @allure.title("When every SceneNPC's UUID is unknown, the formatter falls back to 'None'")
    def test_unregistered_npcs_return_none(self):
        gs = _make_game_state_with_npcs([])
        scene = Scene(
            location_id=_LOC,
            npcs_present=[SceneNPC(role=_GUARD, uuid=make_uuid("ghost-uuid"))],
        )
        assert format_npcs_present(scene, gs) == "None"

    @allure.title("When the scene is None, the NPC-present formatter returns the literal string 'None'")
    def test_no_scene_returns_none(self):
        gs = _make_game_state_with_npcs([])
        assert format_npcs_present(None, gs) == "None"


@allure.epic("NPC Interaction")
@allure.feature("Director context formatting")
@allure.story("Turn log snapshot")
class TestAppendTurnLogsVisibleEntities:
    @allure.title("sync_context sends recent scene-action log entries to the Director prompt")
    def test_sync_context_includes_scene_action_log_history(self) -> None:
        gs = _make_game_state_with_npcs([])
        gs.scene_action_log.append(
            SceneActionEntry(
                actor_kind=ActorKind.PLAYER,
                actor_uuid=gs.player.uuid,
                actor_name=gs.player.name,
                action_type="EXPLORE",
                description="I mark the loose blue tile with chalk.",
                game_clock=gs.game_clock,
            ),
        )
        performer = _CapturingPerformer()

        ContextFormatter(gs).sync_context(performer)

        assert (
            performer.kwargs["scene_history_summary"]
            == "- Player looks around, doing: I mark the loose blue tile with chalk."
        )

    @allure.title("append_turn_logs snapshots last_visible_entities into the new conversation_log entry")
    def test_visible_entities_serialized_into_log(self) -> None:
        gs = _make_game_state_with_npcs([])
        gs.last_visible_entities = [
            VisibleEntity(kind="npc", id="npc-1", names=["an armed man"]),
            VisibleEntity(kind="poi", id="poi-1", names=["notice board", "board"]),
        ]
        ContextFormatter(gs).append_turn_logs("look", "You see the gate.", "EXPLORE")
        entry = gs.conversation_log[-1]
        assert entry["visible_entities"] == [
            {"kind": "npc", "id": "npc-1", "names": ["an armed man"]},
            {"kind": "poi", "id": "poi-1", "names": ["notice board", "board"]},
        ]

    @allure.title("append_turn_logs writes an empty visible_entities list when the narrator produced none")
    def test_empty_visible_entities_still_serialized(self) -> None:
        gs = _make_game_state_with_npcs([])
        ContextFormatter(gs).append_turn_logs("look", "Silence.", "EXPLORE")
        assert gs.conversation_log[-1]["visible_entities"] == []


@allure.epic("NPC Interaction")
@allure.feature("Director context formatting")
@allure.story("Player character context")
class TestPlayerCharacterContext:
    @allure.title("format_player_appearance returns 'unremarkable' when the player has no appearance set")
    def test_default_appearance(self):
        player = PlayerState()
        assert format_player_appearance(player) == "unremarkable"

    @allure.title("format_player_appearance returns the player's appearance verbatim when set")
    def test_appearance_round_trip(self):
        player = PlayerState(appearance="grey hoodie")
        assert format_player_appearance(player) == "grey hoodie"

    @allure.title("format_player_inventory returns 'nothing of note' for an empty inventory")
    def test_default_inventory(self):
        player = PlayerState()
        assert format_player_inventory(player) == "nothing of note"

    @allure.title("format_player_inventory comma-joins inventory items in their stored order")
    def test_inventory_joined(self):
        player = PlayerState(inventory=["phone", "keys"])
        assert format_player_inventory(player) == "phone, keys"

    @allure.title("ContextFormatter.sync_context populates player_appearance and player_inventory on the performer")
    def test_sync_context_sets_player_vars(self):
        gs = _make_game_state_with_npcs([])
        gs.player.appearance = "grey hoodie"
        gs.player.inventory = ["phone", "keys"]

        performer = _CapturingPerformer()
        ContextFormatter(gs).sync_context(performer)

        assert performer.kwargs["player_appearance"] == "grey hoodie"
        assert performer.kwargs["player_inventory"] == "phone, keys"

    @allure.title("ContextFormatter.sync_context exposes technology and social-structure setting context")
    def test_sync_context_sets_setting_worldview_vars(self):
        gs = _make_game_state_with_npcs([])

        performer = _CapturingPerformer()
        ContextFormatter(gs).sync_context(performer)

        assert performer.kwargs["setting_technologies"] == "aqueducts, wax tablets"
        assert performer.kwargs["social_structure"] == "senators, equites, plebs, freedmen, and enslaved people"
