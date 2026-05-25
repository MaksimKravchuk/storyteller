"""Maximal-game-state builder for the consumer-seam contract tests.

Holds only the game-state assembly + knowledge-graph seeding. The
per-performer section-kwargs builders live in
``_consumer_seam_kwargs.py``; the parametrize cases live in
``_consumer_seam_cases.py``. This split keeps each module under the
WPS import-count budget.
"""

from __future__ import annotations

from knowledge.graph import KnowledgeGraph
from knowledge.node import (
    CanonSource,
    EdgeType,
    KnowledgeNode,
    KnowledgeScope,
    KnowledgeSource,
)
from knowledge.scene_state import record_scene_delta
from models.game_state import GameState, PlayerState
from models.goal import Goal, GoalKind, GoalScope, GoalStatus
from models.location import Location
from models.npc_card import NPCCard
from models.scene import PointOfInterest, Scene, SceneNPC
from models.scene_action_log import ActorKind, SceneActionEntry
from models.setting import Setting
from tests._uuid_helpers import make_uuid

LOCATION_ID = make_uuid("forum-loc")
NPC_GUARD_ID = make_uuid("npc-guard")
NPC_TARGET_ID = make_uuid("npc-target")
PLAYER_UUID = make_uuid("player")
PLAYER_NAME = "Player"
FORUM_LOCATION_NAME = "the forum"
MEMORY_TEXT = "The player drew a dagger near the forum steps."


def _make_setting() -> Setting:
    return Setting(
        name="Forum Romanum",
        time_period="AD 64",
        region="Italia",
        summary="Rome under Nero, citizens uneasy after the fire.",
        social_structure="Strict patrician/plebeian hierarchy with slaves.",
    )


def _make_location() -> Location:
    location = Location(uuid=LOCATION_ID, name="The Forum")
    location.object_states["wooden notice board"] = "scorched along its bottom edge"
    return location


def _make_target_npc() -> NPCCard:
    return NPCCard(
        uuid=NPC_TARGET_ID,
        name="Marcus Cinna",
        biography="A patrician with a grudge.",
        appearance="lean, scarred",
        occupation="senator",
        location_id=LOCATION_ID,
    )


def _make_guard_npc() -> NPCCard:
    guard = NPCCard(
        uuid=NPC_GUARD_ID,
        name="Aulus",
        biography="A loyal veteran who survived the Parthian campaign.",
        appearance="tall, armored, with a scar across his cheek",
        short_descriptor="a tall guard in legion armor",
        occupation="city guard",
        personality_traits=["brave", "stern"],
        speech_style="curt",
        inventory=["spear", "shield"],
        current_mood="suspicious",
        physical_status="healthy",
        hostility_level=2,
        recent_hostile_actions=[{"description": "player drew a dagger nearby"}],
        location_id=LOCATION_ID,
    )
    guard.tactical_goal = Goal(
        kind=GoalKind.PURSUE,
        description="Watch the suspicious patrician.",
        scope=GoalScope.LIFE,
        status=GoalStatus.ACTIVE,
        target_uuid=NPC_TARGET_ID,
        turns_pursued=2,
        last_attempted_action="STEALTH near the notice board",
        progress_notes=["target lingered by the forum steps"],
    )
    return guard


def _seed_actor_knowledge(graph: KnowledgeGraph) -> None:
    """Seed knowledge + a personal memory so the Actor prompt has both."""
    graph.register_actor_node(NPC_GUARD_ID, label="Aulus (city guard)")
    fact_node = KnowledgeNode(
        text="The forum closes at dusk.",
        scope=KnowledgeScope.LOCAL,
        source=KnowledgeSource.FACT,
        canon=CanonSource.HISTORICAL,
        location_id=LOCATION_ID,
    )
    graph.add_node(fact_node)
    memory_node = KnowledgeNode(
        text=MEMORY_TEXT,
        scope=KnowledgeScope.LOCAL,
        source=KnowledgeSource.PERSONAL_EXPERIENCE,
        canon=CanonSource.SESSION,
        location_id=LOCATION_ID,
    )
    memory_uuid = graph.add_node(memory_node)
    graph.add_edge(NPC_GUARD_ID, memory_uuid, EdgeType.WITNESSED)


def _make_player() -> PlayerState:
    return PlayerState(
        name=PLAYER_NAME,
        location_id=LOCATION_ID,
        inventory=["dagger", "purse"],
        appearance="a wiry traveller in a dusty tunic",
        known_npcs={NPC_GUARD_ID},
    )


def _make_current_scene() -> Scene:
    return Scene(
        location_id=LOCATION_ID,
        description="A wide forum lit by torches, smoke still in the air.",
        npcs_present=[
            SceneNPC(role="city guard", uuid=NPC_GUARD_ID),
            SceneNPC(role="senator", uuid=NPC_TARGET_ID),
        ],
        points_of_interest=[PointOfInterest(names=["wooden notice board"])],
        ambient_description="The crackle of dying flames, ash on stone.",
    )


def _make_scene_action_entry() -> SceneActionEntry:
    return SceneActionEntry(
        actor_kind=ActorKind.PLAYER,
        actor_uuid=PLAYER_UUID,
        actor_name=PLAYER_NAME,
        action_type="EXPLORE",
        description="Looked around the smoke-filled forum.",
        game_clock=float(0),
    )


def build_maximal_game_state() -> GameState:
    """Build a GameState satisfying every PromptSection's preconditions.

    See ``tests/prompts/test_consumer_seam_contract.py`` module docstring
    for the full enumeration of which sections each precondition enables.
    """
    graph = KnowledgeGraph()
    record_scene_delta(
        graph,
        location_id=LOCATION_ID,
        delta_text="The notice board scorched after the player's torch fell.",
    )
    _seed_actor_knowledge(graph)

    state = GameState(
        setting=_make_setting(),
        knowledge_graph=graph,
        player=_make_player(),
        locations={LOCATION_ID: _make_location()},
        npcs={NPC_GUARD_ID: _make_guard_npc(), NPC_TARGET_ID: _make_target_npc()},
    )
    state.world_state.world_mood = "tense, smoke-tinged"
    state.current_scene = _make_current_scene()
    state.scene_action_log.append(_make_scene_action_entry())
    return state
