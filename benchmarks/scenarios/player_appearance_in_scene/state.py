"""Seed state builder for the player-appearance scenario.

A foreign-looking visitor — tall, fair-skinned, dressed in heavy wolf furs,
speaking Latin with a heavy northern accent — approaches a Roman fruit
seller in the Forum marketplace. The NPC has no pre-loaded relationship
with the player and no goals; the only signal she can react to is the
literary :class:`cast.player_context.PlayerUtterance` rendering of the
player's actions, which carries the appearance into every turn she sees.
"""

from __future__ import annotations

from uuid import UUID

from benchmarks._uuid_helpers import make_uuid
from benchmarks.harness.types._scenarios import ScenarioState
from knowledge.graph import KnowledgeGraph
from models.game_state import GameState, PlayerState
from models.location import Location
from models.npc_card import NPCCard
from models.scene import PointOfInterest, Scene, SceneNPC
from models.setting import Setting

_CASSIA_UUID = make_uuid("npc-cassia-fruitseller")

_PLAYER_APPEARANCE = (
    "tall and broad-shouldered, fair-skinned with long pale hair, dressed in "
    "heavy wolf furs and rough hide boots; speaks Latin with a heavy northern accent"
)


def _make_setting() -> Setting:
    return Setting(
        name="Ancient Rome",
        time_period="1st century AD",
        region="Italy",
        summary=(
            "The Roman Empire under the early principate — a dense, bustling, "
            "politically tense city where olive-skinned Latins and Greeks predominate "
            "and northern barbarians are an exotic, often unsettling sight."
        ),
    )


def _make_cassia() -> NPCCard:
    """Build the Cassia card — a routine Roman fruit seller, no pre-loaded bias."""
    cassia = NPCCard(
        name="Cassia",
        biography=(
            "A middle-aged Roman widow who runs a fruit stall at the Forum. She has "
            "spent her whole life in the city and has rarely seen anyone from beyond "
            "the empire's northern frontier."
        ),
        appearance="Olive-skinned, dark hair pinned back, simple linen stola, work-worn hands.",
        occupation="fruit seller",
        personality_traits=["sharp-tongued", "observant", "shrewd"],
        speech_style="brisk Roman vendor patter — direct, transactional, occasionally curious",
        knowledge_scope="local",
        conversation_history=[],
        current_mood="neutral",
        physical_status="healthy",
    )
    cassia.uuid = _CASSIA_UUID
    return cassia


def _make_location() -> Location:
    return Location(
        name="Roman Forum marketplace",
        description="A sun-bright plaza of stalls and pillars, dense with shoppers and the smell of bread and fruit.",
        location_type="district",
        tags=["market", "forum", "city"],
        points_of_interest=[
            PointOfInterest(names=["fruit stall"]),
            PointOfInterest(names=["fountain"]),
            PointOfInterest(names=["statue of Caesar"]),
        ],
    )


def _make_scene(location_id: UUID, cassia_uuid: UUID) -> Scene:
    return Scene(
        location_id=location_id,
        description=(
            "The Forum is noisy with vendors and shoppers. Cassia stands behind her fruit stall, "
            "weighing pomegranates, eyeing the crowd."
        ),
        npcs_present=[SceneNPC(role="fruit seller", uuid=cassia_uuid)],
        points_of_interest=[
            PointOfInterest(names=["fruit stall"]),
            PointOfInterest(names=["fountain"]),
            PointOfInterest(names=["statue of Caesar"]),
        ],
        ambient_description="Midday sun, smell of bread and fruit, a murmur of Latin bargaining.",
        time_of_day="midday",
    )


def build_state() -> ScenarioState:
    """Construct the seed :class:`GameState` for this scenario."""
    cassia = _make_cassia()
    location = _make_location()
    cassia.location_id = location.uuid

    game_state = GameState(
        setting=_make_setting(),
        knowledge_graph=KnowledgeGraph(),
        player=PlayerState(
            name="Bjorn",
            location_id=location.uuid,
            appearance=_PLAYER_APPEARANCE,
        ),
    )
    game_state.locations[location.uuid] = location
    game_state.npcs[cassia.uuid] = cassia
    game_state.current_scene = _make_scene(location.uuid, cassia.uuid)
    game_state.game_clock = 10.0
    game_state.game_time = "morning"
    return ScenarioState(game_state=game_state, events=[])
