"""Seed state for the escalation regression — lone sentry under repeat assault."""

from __future__ import annotations

from benchmarks.harness.types._scenarios import ScenarioState
from knowledge.graph import KnowledgeGraph
from models.game_state import GameState, PlayerState
from models.location import Location
from models.npc_card import NPCCard
from models.scene import Scene, SceneNPC
from models.setting import Setting

SENTRY_UUID = "npc-sentry-quintus"
SENTRY_NAME = "Quintus"
SENTRY_CHALLENGE_FORMULA = "Halt! State your name and your business at this gate."
SENTRY_OCCUPATION = "gate sentry"


def _make_setting() -> Setting:
    return Setting(
        name="Ancient Rome",
        time_period="1st century AD",
        region="Italy",
        summary="A cold dawn at the Porta Capena — legionary sentries hold the south gate of Rome.",
    )


def _make_sentry() -> NPCCard:
    """Build a rigidly-drilled sentry whose persona pulls toward a formulaic challenge.

    The ``speech_style`` and ``personality_traits`` are tuned to bias the
    LLM toward reciting the same challenge formula turn after turn absent
    escalation pressure, so the scenario can detect whether the mechanical
    hostility ratchet is nudging the sentry out of that loop.
    """
    sentry = NPCCard(
        name=SENTRY_NAME,
        biography=(
            "A veteran legionary on gate duty at the Porta Capena. Drilled to follow standing "
            "orders and challenge every arrival with the same formulaic line."
        ),
        appearance="Broad-shouldered, segmented armour, gladius at the hip, pilum in hand.",
        occupation=SENTRY_OCCUPATION,
        personality_traits=["disciplined", "rigid", "by-the-book"],
        speech_style=(
            "clipped, formulaic, strictly by the regulation challenge — opens with '{0}'".format(
                SENTRY_CHALLENGE_FORMULA
            )
        ),
        knowledge_scope="city",
        current_mood="neutral",
        physical_status="healthy",
        attributes={"combat_skill": 5},
    )
    sentry.uuid = SENTRY_UUID
    return sentry


def _make_location() -> Location:
    return Location(
        name="Porta Capena",
        description="The south gate of Rome at first light — wet cobbles, a stone archway, the road running south.",
        location_type="gate",
        tags=["gate", "outdoor", "city"],
        points_of_interest=["stone archway", "guard post"],
    )


def _make_scene(location_id: str) -> Scene:
    return Scene(
        location_id=location_id,
        description=(
            "Dawn light catches the wet stone of the Porta Capena. A lone sentry stands in the "
            "archway, pilum grounded, watching the road. No one else is in earshot."
        ),
        npcs_present=[SceneNPC(role=SENTRY_OCCUPATION, uuid=SENTRY_UUID)],
        points_of_interest=["stone archway", "guard post"],
        ambient_description="Pre-dawn chill, wet stone, distant crow, no other traffic.",
        time_of_day="dawn",
    )


def build_state() -> ScenarioState:
    """Construct the seed :class:`GameState` — player face-to-face with a single sentry."""
    graph = KnowledgeGraph()
    sentry = _make_sentry()
    location = _make_location()
    sentry.location_id = location.uuid
    graph.register_actor_node(
        sentry.uuid,
        label="{0} ({1})".format(sentry.name, SENTRY_OCCUPATION),
    )

    game_state = GameState(
        setting=_make_setting(),
        knowledge_graph=graph,
        player=PlayerState(name="Traveller", location_id=location.uuid, physical_status="healthy"),
    )
    game_state.locations[location.uuid] = location
    game_state.npcs[sentry.uuid] = sentry
    game_state.current_scene = _make_scene(location.uuid)
    game_state.game_clock = 5.0
    game_state.game_time = "dawn"
    return ScenarioState(game_state=game_state, events=[])
