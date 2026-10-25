"""Regression: an NPC met at a place is the same NPC when the player comes back.

Production bug (2026-10-25): the player told Eira their name and their
missing brother's story, walked up the village path, came back to the
landing and asked her about it. Every MOVE rebuilt the scene from
free-text roles, so the landing was repopulated with freshly generated
NPCs (including a second "Eira") and the original Eira — who held the
memory — never came back. These tests drive ``PlanExecutor`` through
TALK → MOVE away → MOVE back → TALK and read the returning NPC's Actor
prompt (the consumer seam), not just the supplier-side graph.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import allure
import pytest

from cast import (
    actor as actor_mod,
    director_dialogue,
    director_events,
    director_execution,
    director_retaliation,
    npc_ticker,
    npc_turn,
    scene_place,
)
from cast._scene_location import UNKNOWN_SCENE_LOCATION
from knowledge import graph as graph_mod, memory as memory_mod, query as query_mod
from models import game_state as gs_mod, location as location_mod, npc_card as npc_card_mod, scene as scene_mod
from tests.director_helpers import make_setting, make_uuid, route_plan
from tests.prompts import _consumer_seam_kwargs as kwargs_mod
from timeline.event_manager import EventManager

NPCCard = npc_card_mod.NPCCard
Scene = scene_mod.Scene
SceneNPC = scene_mod.SceneNPC

_LANDING = make_uuid("place-landing")
_EIRA = make_uuid("place-eira")
_PLAYER = make_uuid("place-player")
_SUMMARY = "Elias Grey told Eira his brother Tomas sailed on the Gull and never came back."


class _World:
    """Bundle of the live objects one test drives."""

    def __init__(self) -> None:
        self.gs = gs_mod.GameState(setting=make_setting(), knowledge_graph=graph_mod.KnowledgeGraph())
        self.gs.game_time = "afternoon"
        self.gs.player.uuid = _PLAYER
        self.gs.player.name = "Elias Grey"
        landing = location_mod.Location(uuid=_LANDING, name="Fjordside Landing")
        self.gs.locations[_LANDING] = landing
        self.gs.player.location_id = _LANDING
        self.actors: dict[Any, Any] = {}
        self.eira_llm = kwargs_mod.make_mock_llm(kwargs_mod.ACTOR_REPLY_JSON)
        eira = NPCCard(name="Eira", occupation="net-mender", location_id=_LANDING)
        eira.uuid = _EIRA
        self.register(eira, llm=self.eira_llm)
        self.gs.current_scene = Scene(
            location_id=_LANDING,
            description="A snowy landing.",
            npcs_present=[SceneNPC(role="net-mender", uuid=_EIRA)],
        )

    def register(self, card: NPCCard, llm: Any | None = None) -> None:
        """Mirror ``Director._register_new_npc``: state, location, graph node, Actor."""
        self.gs.npcs[card.uuid] = card
        location = self.gs.locations.get(card.location_id) if card.location_id else None
        if location is not None:
            location.add_npc(card.uuid)
        self.gs.knowledge_graph.register_actor_node(card.uuid, label=card.name)
        self.actors[card.uuid] = actor_mod.Actor(
            llm_client=llm or kwargs_mod.make_mock_llm(kwargs_mod.ACTOR_REPLY_JSON),
            npc=card,
            knowledge_query=query_mod.KnowledgeQueryEngine(self.gs.knowledge_graph),
            language="English",
        )


def _generate_cards(world: _World, input_data: list[str]) -> list[NPCCard]:
    """Stand-in NPCGenerator: stamps the scene's location like the real one.

    A re-described net-mender comes back as another "Eira", exactly as the
    production LLM did when the Scene Builder listed her role again.
    """
    location_id = world.gs.current_scene.location_id if world.gs.current_scene else None
    cards = []
    for role in input_data:
        name = "Eira" if "net-mender" in role else "Hilde"
        card = NPCCard(name=name, occupation=role, location_id=location_id)
        card.uuid = make_uuid("generated-{0}".format(role))
        cards.append(card)
    return cards


def _build_executor(world: _World, scenes: list[Scene]) -> director_execution.PlanExecutor:
    gs = world.gs
    mem_mgr = memory_mod.MemoryManager(graph=gs.knowledge_graph, llm_client=kwargs_mod.make_mock_llm(_SUMMARY))
    event_mgr = EventManager(game_state=gs, knowledge_graph=gs.knowledge_graph)
    scene_builder = AsyncMock()
    scene_builder.execute = AsyncMock(side_effect=scenes)
    npc_generator = AsyncMock()
    npc_generator.execute = AsyncMock(side_effect=lambda input_data, context: _generate_cards(world, input_data))
    narrator = AsyncMock()
    narrator.execute = AsyncMock(return_value="Narrated.")
    return director_execution.PlanExecutor(
        game_state=gs,
        events=director_events.EventProcessor(gs, event_mgr, mem_mgr),
        event_manager=event_mgr,
        dialogue=director_dialogue.DialogueHandler(gs, world.actors, mem_mgr),
        retaliation=director_retaliation.RetaliationHandler(gs, world.actors),
        npc_turns=npc_turn.NPCTurnResolver(gs, world.actors),
        npc_ticker=npc_ticker.NPCTicker(gs),
        memory_manager=mem_mgr,
        scene_builder=scene_builder,
        narrator=narrator,
        npc_generator=npc_generator,
        data_miner=AsyncMock(),
        item_generator=None,
        register_npc_fn=world.register,
    )


def _path_scene() -> Scene:
    return Scene(
        location_id=UNKNOWN_SCENE_LOCATION,
        place_name="Upper village path",
        description="A narrow path between turf-roofed houses.",
        npcs_present=[SceneNPC(role="smith")],
    )


def _landing_return_scene() -> Scene:
    # The Scene Builder recognised the known place and copied its id, but
    # still re-described the woman mending nets as a fresh role.
    return Scene(
        location_id=_LANDING,
        description="The snowy landing again.",
        npcs_present=[SceneNPC(role="net-mender woman")],
    )


async def _play(executor: director_execution.PlanExecutor, plan: Any, action: str) -> None:
    await executor.execute_plan(plan=plan, player_action=action, completed_events=[], run_npc_turns=False)


async def _leave_and_return(executor: director_execution.PlanExecutor) -> None:
    await _play(
        executor,
        route_plan("TALK", targets=["Eira"], delegate=["actor"]),
        "My name is Elias Grey. My brother Tomas sailed on the Gull and never came back.",
    )
    await _play(executor, route_plan("MOVE", direction="up the path"), "I walk up the village path.")
    await _play(executor, route_plan("MOVE", direction="the landing"), "I walk back down to the landing.")


@allure.epic("Memory & Persistence")
@allure.feature("NPC place persistence")
class TestReturningToAPlace:
    @allure.story("Leave and return")
    @allure.title("The NPC the player talked to is back in the scene when the player returns")
    @pytest.mark.asyncio
    async def test_resident_npc_returns_with_same_identity(self) -> None:
        world = _World()
        executor = _build_executor(world, [_path_scene(), _landing_return_scene()])

        await _leave_and_return(executor)

        scene = world.gs.current_scene
        assert scene is not None
        assert world.gs.player.location_id == _LANDING
        assert _EIRA in {snpc.uuid for snpc in scene.npcs_present}
        assert [npc.name for npc in world.gs.npcs.values()].count("Eira") == 1

    @allure.story("Leave and return")
    @allure.title("The returning NPC's Actor prompt carries the memory of the first conversation")
    @pytest.mark.asyncio
    async def test_returning_npc_prompt_recalls_first_conversation(self) -> None:
        world = _World()
        executor = _build_executor(world, [_path_scene(), _landing_return_scene()])
        await _leave_and_return(executor)
        world.eira_llm.send_message.reset_mock()

        await _play(executor, route_plan("TALK", targets=["Eira"], delegate=["actor"]), "Do you remember me?")

        assert _SUMMARY in kwargs_mod.capture_system_prompt(world.eira_llm)

    @allure.story("Leave and return")
    @allure.title("Walking to a new place registers it as a location connected to where the player came from")
    @pytest.mark.asyncio
    async def test_new_place_becomes_connected_location(self) -> None:
        world = _World()
        executor = _build_executor(world, [_path_scene()])

        await _play(executor, route_plan("MOVE", direction="up the path"), "I walk up the village path.")

        path_id = world.gs.player.location_id
        assert path_id is not None
        assert path_id not in {_LANDING, UNKNOWN_SCENE_LOCATION}
        path = world.gs.locations[path_id]
        assert path.name == "Upper village path"
        assert _LANDING in path.connected_locations
        assert path_id in world.gs.locations[_LANDING].connected_locations
        assert world.gs.current_scene is not None
        assert world.gs.current_scene.location_id == path_id
        smith = next(npc for npc in world.gs.npcs.values() if npc.occupation == "smith")
        assert smith.location_id == path_id


@allure.epic("Memory & Persistence")
@allure.feature("NPC place persistence")
class TestCallingOutToAResident:
    @allure.story("Name targeting")
    @allure.title("Addressing a resident by name who is not seated brings that NPC into the scene, not a namesake")
    def test_resident_named_target_joins_scene(self) -> None:
        world = _World()
        world.gs.current_scene = Scene(location_id=_LANDING, description="An empty landing.")
        handler = director_dialogue.DialogueHandler(world.gs, world.actors, AsyncMock())

        handler.ensure_targets_in_scene(["Eira", "the ferryman"])

        assert [(snpc.role, snpc.uuid) for snpc in world.gs.current_scene.npcs_present] == [
            ("Eira", _EIRA),
            ("the ferryman", None),
        ]


@allure.epic("Memory & Persistence")
@allure.feature("NPC place persistence")
class TestWalkingBackToAnNPC:
    @allure.story("Leave and return")
    @allure.title("Walking back to an NPC who is not in the current scene travels instead of staying put")
    @pytest.mark.asyncio
    async def test_move_toward_absent_npc_rebuilds_scene(self) -> None:
        world = _World()
        executor = _build_executor(world, [_path_scene(), _landing_return_scene()])
        await _play(executor, route_plan("MOVE", direction="up the path"), "I walk up the village path.")

        await _play(
            executor,
            route_plan("MOVE", direction="the landing", targets=["Eira"]),
            "I walk back down to the landing where Eira mends her net.",
        )

        assert world.gs.player.location_id == _LANDING
        assert world.gs.current_scene is not None
        assert _EIRA in {snpc.uuid for snpc in world.gs.current_scene.npcs_present}


@allure.epic("Memory & Persistence")
@allure.feature("NPC place persistence")
class TestResidentWandersOff:
    @allure.story("Residency")
    @allure.title("A resident who walks off on their own turn leaves the scene but keeps their place and comes back")
    def test_autonomous_move_keeps_residency(self) -> None:
        world = _World()

        npc_turn._apply_scene_mutation(_EIRA, "MOVE", "up the path", world.gs)

        assert world.gs.current_scene is not None
        assert _EIRA not in {snpc.uuid for snpc in world.gs.current_scene.npcs_present}
        assert _EIRA in world.gs.locations[_LANDING].npcs_present
        later = Scene(location_id=_LANDING, description="The landing, later.")
        scene_place.enter_scene(world.gs, later, allow_new_place=True)
        assert _EIRA in {snpc.uuid for snpc in later.npcs_present}

    @allure.story("Name targeting")
    @allure.title("Calling for an NPC who lives elsewhere never spawns a stranger for their name")
    def test_known_name_elsewhere_spawns_no_stranger(self) -> None:
        world = _World()
        path = location_mod.Location(name="Upper path")
        world.gs.locations[path.uuid] = path
        world.gs.player.location_id = path.uuid
        world.gs.current_scene = Scene(location_id=path.uuid, description="A path.")
        handler = director_dialogue.DialogueHandler(world.gs, world.actors, AsyncMock())

        handler.ensure_targets_in_scene(["Eira"])

        assert world.gs.current_scene.npcs_present == []
