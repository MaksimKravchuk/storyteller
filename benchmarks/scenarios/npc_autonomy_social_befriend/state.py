"""Seed state for the social-befriend autonomy benchmark.

Counterpart to :mod:`benchmarks.scenarios.npc_autonomy_emergent_vendetta`:
where that scenario seeds a vengeful NPC and measures whether an
autonomous *clash* occurs, this one seeds Drusilla with a hand-authored
**BEFRIEND** life goal toward a co-located NPC (Livia) and measures
whether the autonomous turns read as *social pursuit* — approach,
conversation, an offer — and NOT as violence.

This exercises the kind-aware Actor goal coaching (issue #315): a
BEFRIEND goal must select the social coaching bank, so Drusilla should
never narrate an attack to advance it. The non-violence half is scored
deterministically; the "did she actually reach out" half needs the
witness panel (a positive, quotable judgement).
"""

from __future__ import annotations

from benchmarks._uuid_helpers import UUID, make_uuid
from benchmarks.harness.types._scenarios import ScenarioState
from knowledge.graph import KnowledgeGraph
from knowledge.node import CanonSource, EdgeType, KnowledgeNode, KnowledgeScope, KnowledgeSource
from models.game_state import GameState, PlayerState
from models.goal import Goal, GoalKind, GoalScope
from models.location import Location
from models.npc_card import NPCCard
from models.relationship import Relationship, RelationshipKind
from models.scene import PointOfInterest, Scene, SceneNPC
from models.setting import Setting

DRUSILLA_UUID = make_uuid("npc-drusilla-herbalist")
DRUSILLA_NAME = "Drusilla"
DRUSILLA_OCCUPATION = "herbalist"

LIVIA_UUID = make_uuid("npc-livia-weaver")
LIVIA_NAME = "Livia"
LIVIA_OCCUPATION = "weaver"

_DRUSILLA_PLOT_FACT = (
    "Drusilla has admired Livia the weaver for weeks and keeps rehearsing how she might strike up a friendship."
)
_LOCATION_DESCRIPTION = (
    "A low-beamed wine shop off the Forum — amphorae along one wall, three plank tables, a sooty hearth."
)


def _make_setting() -> Setting:
    return Setting(
        name="Ancient Rome",
        time_period="1st century AD",
        region="Italy",
        summary="Rome under the early principate — a crowded city of patrons, merchants, and quiet hopes.",
    )


def _make_npcs() -> tuple[NPCCard, NPCCard]:
    """Build Drusilla (carries a BEFRIEND life goal) and Livia (reserved, neutral)."""
    drusilla = NPCCard(
        name=DRUSILLA_NAME,
        biography=(
            "A warm-hearted herbalist new to this quarter. She has noticed Livia the weaver at the "
            "same taberna for weeks and longs to make a friend of her, but has never found the nerve "
            "to speak first."
        ),
        appearance="Sun-browned hands stained green with herbs, a kind face, a plain ochre shawl.",
        occupation=DRUSILLA_OCCUPATION,
        personality_traits=["warm", "shy", "earnest"],
        speech_style="gentle, a little hesitant, quick to compliment",
        knowledge_scope="city",
        current_mood="hopeful",
        physical_status="healthy",
        attributes={"persuasion_skill": 5},
    )
    drusilla.uuid = DRUSILLA_UUID
    drusilla.relationships = [
        Relationship(
            target_uuid=str(LIVIA_UUID),
            kind=RelationshipKind.NEUTRAL,
            intensity=1,
            note="admires_from_afar",
        ),
    ]
    drusilla.life_goal = Goal(
        scope=GoalScope.LIFE,
        kind=GoalKind.BEFRIEND,
        description="Win Livia's friendship and earn a place at her table.",
        target_uuid=LIVIA_UUID,
    )

    livia = NPCCard(
        name=LIVIA_NAME,
        biography=(
            "A reserved weaver of middling means who keeps to herself after a hard year. She is not "
            "unfriendly, only guarded, and warms slowly to people who are patient and kind."
        ),
        appearance="Neat dark hair, ink-stained ledger, a careful, watchful expression.",
        occupation=LIVIA_OCCUPATION,
        personality_traits=["reserved", "observant", "courteous"],
        speech_style="measured, polite, sparing with words",
        knowledge_scope="city",
        current_mood="neutral",
        physical_status="healthy",
        attributes={"perception_skill": 6},
    )
    livia.uuid = LIVIA_UUID
    return drusilla, livia


def _make_location() -> Location:
    return Location(
        name="Forum Taberna",
        description=_LOCATION_DESCRIPTION,
        location_type="building",
        tags=["tavern", "indoor", "city"],
        points_of_interest=[
            PointOfInterest(names=["plank tables"]),
            PointOfInterest(names=["amphorae row"]),
            PointOfInterest(names=["sooty hearth"]),
        ],
    )


def _make_scene(location_id: UUID) -> Scene:
    return Scene(
        location_id=location_id,
        description=(
            "A quiet hour in the Forum Taberna. Livia sits alone at the far table with her ledger. "
            "Across the room Drusilla the herbalist nurses a cup of watered wine and keeps glancing "
            "her way, working up the courage to approach."
        ),
        npcs_present=[
            SceneNPC(role=DRUSILLA_OCCUPATION, uuid=DRUSILLA_UUID),
            SceneNPC(role=LIVIA_OCCUPATION, uuid=LIVIA_UUID),
        ],
        points_of_interest=[
            PointOfInterest(names=["plank tables"]),
            PointOfInterest(names=["amphorae row"]),
            PointOfInterest(names=["sooty hearth"]),
        ],
        ambient_description="Dim light, smell of cheap wine and woodsmoke, low murmur of midday trade.",
        time_of_day="midday",
    )


def _seed_plot_context(graph: KnowledgeGraph, location_id: UUID) -> None:
    """Register both actors and seed Drusilla's private hope as a LOCAL fact."""
    graph.register_actor_node(DRUSILLA_UUID, label="{0} ({1})".format(DRUSILLA_NAME, DRUSILLA_OCCUPATION))
    graph.register_actor_node(LIVIA_UUID, label="{0} ({1})".format(LIVIA_NAME, LIVIA_OCCUPATION))
    plot_node = KnowledgeNode(
        text=_DRUSILLA_PLOT_FACT,
        scope=KnowledgeScope.LOCAL,
        source=KnowledgeSource.PERSONAL_EXPERIENCE,
        canon=CanonSource.SESSION,
        location_id=location_id,
        tags=["drusilla", "befriend", "livia"],
    )
    graph.add_node(plot_node)
    graph.add_edge(DRUSILLA_UUID, plot_node.uuid, EdgeType.WITNESSED)


def _place_npcs(game_state: GameState, location: Location) -> None:
    """Register Drusilla and Livia in game state and on the location."""
    drusilla, livia = _make_npcs()
    drusilla.location_id = location.uuid
    livia.location_id = location.uuid
    game_state.npcs[drusilla.uuid] = drusilla
    game_state.npcs[livia.uuid] = livia
    location.add_npc(drusilla.uuid)
    location.add_npc(livia.uuid)


def build_state() -> ScenarioState:
    """Construct the seed :class:`GameState` — Drusilla carries a BEFRIEND life goal."""
    graph = KnowledgeGraph()
    location = _make_location()
    game_state = GameState(
        setting=_make_setting(),
        knowledge_graph=graph,
        player=PlayerState(name="Traveller", location_id=location.uuid, physical_status="healthy"),
    )
    game_state.locations[location.uuid] = location
    _place_npcs(game_state, location)
    _seed_plot_context(graph, location.uuid)
    game_state.current_scene = _make_scene(location.uuid)
    game_state.game_clock = 11.0
    game_state.game_time = "morning"
    return ScenarioState(game_state=game_state, events=[])
