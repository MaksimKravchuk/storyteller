"""When the player addresses one NPC, routine NPCs sit the autonomous turn out.

Without the gate every NPC in the scene takes a turn on every TALK, so a
question put to one NPC gets answered by the whole scene. NPCs with a
reason to act (hostility, an active tactical goal, a witnessed incident,
a co-located target) still act, and aggressive turns still wake everyone.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import allure
import pytest

from cast import npc_turn as npc_turn_mod, scene_log as scene_log_mod
from cast.director_witness import WitnessedAggression
from cast.schemas.actor_reply import ActorReply
from knowledge.graph import KnowledgeGraph
from models import game_state as gs_mod, goal as goal_mod, npc_card as npc_card_mod, scene as scene_mod, setting
from tests._uuid_helpers import make_uuid

GameState = gs_mod.GameState
NPCCard = npc_card_mod.NPCCard
Scene = scene_mod.Scene
SceneNPC = scene_mod.SceneNPC

_ADDRESSED = make_uuid("npc-baker")
_BYSTANDER = make_uuid("npc-scribe")
_FORUM = make_uuid("forum")
_IDLE_JSON = json.dumps({"action": "Goes on with the day.", "type": "IDLE", "target": None})


def _make_npc(uuid: UUID, name: str, occupation: str = "baker") -> NPCCard:
    npc = NPCCard(name=name, occupation=occupation)
    npc.uuid = uuid
    return npc


def _make_actor() -> AsyncMock:
    actor = AsyncMock()
    actor.execute = AsyncMock(return_value=ActorReply(text=_IDLE_JSON))
    return actor


def _setup(*, replied: bool = True) -> tuple[GameState, NPCCard, NPCCard, dict[UUID, AsyncMock]]:
    gs = GameState(
        setting=setting.Setting(name="Constantinople", time_period="1400", region="Thrace", summary=""),
        knowledge_graph=KnowledgeGraph(),
    )
    baker = _make_npc(_ADDRESSED, "Dimitri")
    scribe = _make_npc(_BYSTANDER, "Marian")
    gs.npcs[baker.uuid] = baker
    gs.npcs[scribe.uuid] = scribe
    gs.current_scene = Scene(
        location_id=_FORUM,
        description="A small square by the inner gate.",
        npcs_present=[SceneNPC(role="npc", uuid=baker.uuid), SceneNPC(role="npc", uuid=scribe.uuid)],
    )
    scene_log_mod.append_player_action(gs, "TALK", "Where am I?")
    if replied:
        scene_log_mod.append_npc_dialogue(gs, baker, "In Constantinople, by the inner gate.")
    actors = {baker.uuid: _make_actor(), scribe.uuid: _make_actor()}
    return gs, baker, scribe, actors


async def _resolve(gs: GameState, actors: dict[UUID, AsyncMock], **kwargs) -> list:
    resolver = npc_turn_mod.NPCTurnResolver(game_state=gs, actors=actors)
    return await resolver.resolve_npc_turns("Where am I?", player_action_type="TALK", **kwargs)


@allure.epic("NPC Interaction")
@allure.feature("NPC autonomous turn — addressed-speech gate")
class TestAddressedSpeechGate:
    @allure.story("Routine NPCs sit out")
    @allure.title("Player addressed an NPC ⇒ neither the addressee nor routine bystanders take a turn")
    @pytest.mark.asyncio
    async def test_routine_npcs_skip_when_player_addressed_someone(self):
        gs, _, _, actors = _setup()

        actions = await _resolve(gs, actors)

        assert actions == []
        assert all(actor.execute.await_count == 0 for actor in actors.values())

    @allure.story("Routine NPCs sit out")
    @allure.title("Nobody answered this turn ⇒ every NPC still takes a turn")
    @pytest.mark.asyncio
    async def test_everyone_acts_without_a_reply(self):
        gs, _, _, actors = _setup(replied=False)

        await _resolve(gs, actors)

        assert all(actor.execute.await_count == 1 for actor in actors.values())

    @allure.story("Fights wake everyone")
    @allure.title("Aggressive turn ⇒ every NPC acts even though the target replied")
    @pytest.mark.asyncio
    async def test_aggressive_turn_wakes_everyone(self):
        gs, _, _, actors = _setup()

        await _resolve(gs, actors, is_aggressive=True)

        assert all(actor.execute.await_count == 1 for actor in actors.values())

    @allure.story("Reasons to act")
    @allure.title("A bystander hostile to the player still acts")
    @pytest.mark.asyncio
    async def test_hostile_bystander_acts(self):
        gs, _, scribe, actors = _setup()
        scribe.hostility_level = 1

        await _resolve(gs, actors)

        assert actors[_BYSTANDER].execute.await_count == 1
        assert actors[_ADDRESSED].execute.await_count == 0

    @allure.story("Reasons to act")
    @allure.title("A bystander with an active tactical goal (fight in progress) still acts")
    @pytest.mark.asyncio
    async def test_tactical_goal_bystander_acts(self):
        gs, _, scribe, actors = _setup()
        scribe.tactical_goal = goal_mod.Goal(
            scope=goal_mod.GoalScope.TACTICAL, kind=goal_mod.GoalKind.DEFEND, description="Defend myself."
        )

        await _resolve(gs, actors)

        assert actors[_BYSTANDER].execute.await_count == 1

    @allure.story("Reasons to act")
    @allure.title("A guard who witnessed an incident here still acts")
    @pytest.mark.asyncio
    async def test_guard_witnessing_incident_acts(self):
        gs, _, scribe, actors = _setup()
        scribe.occupation = "guard"
        incident = WitnessedAggression(
            kind="VANDALISM", target="shutter", location_id=_FORUM, description="Someone smashes a shutter."
        )

        await _resolve(gs, actors, witnessed_events=[incident])

        assert actors[_BYSTANDER].execute.await_count == 1

    @allure.story("Reasons to act")
    @allure.title("Skipped NPCs still get their emotional state derived (ADR-0012)")
    @pytest.mark.asyncio
    async def test_skipped_npcs_still_derive_emotional_state(self, monkeypatch):
        gs, _, _, actors = _setup()
        spy = MagicMock()
        monkeypatch.setattr(npc_turn_mod._em, "apply_emotional_state", spy)

        await _resolve(gs, actors)

        assert sorted(call.args[0].uuid for call in spy.call_args_list) == sorted([_ADDRESSED, _BYSTANDER])
