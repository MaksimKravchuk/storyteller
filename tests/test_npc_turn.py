"""Tests for NPC autonomous turn resolution."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

import allure
import pytest

from cast.dice import ContestType
from cast import npc_turn as npc_turn_mod
from cast.npc_turn import NPCAction, NPCTurnResolver
from cast.schemas.actor_reply import ActorReply
from knowledge.graph import KnowledgeGraph
from knowledge.node import CanonSource, EdgeType, KnowledgeNode, KnowledgeScope, KnowledgeSource
from models import game_state as gs_mod, npc_card as npc_card_mod, scene as scene_mod, setting as setting_mod

GameState = gs_mod.GameState
NPCCard = npc_card_mod.NPCCard
Scene = scene_mod.Scene
SceneNPC = scene_mod.SceneNPC
Setting = setting_mod.Setting

_NPC_UUID_A = "npc-a"
_NPC_UUID_B = "npc-b"
_GUARD = "Guard"
_MERCHANT = "Merchant"


def _make_gs() -> GameState:
    kg = KnowledgeGraph()
    return GameState(
        setting=Setting(name="Rome", time_period="1 AD", region="Italy", summary=""),
        knowledge_graph=kg,
    )


def _make_npc(uuid: str, name: str, mood: str = "neutral", status: str = "healthy", **attrs) -> NPCCard:
    npc = NPCCard(name=name, occupation="test", attributes=attrs)
    npc.uuid = uuid
    npc.current_mood = mood
    npc.physical_status = status
    return npc


def _make_scene(*npc_uuids: str) -> Scene:
    return Scene(
        location_id="forum",
        description="The bustling Forum.",
        npcs_present=[SceneNPC(role="npc", uuid=uid) for uid in npc_uuids],
    )


def _make_actor(response: dict) -> AsyncMock:
    """Create a mock Actor that returns JSON response wrapped in ActorReply."""
    mock = AsyncMock()
    mock.execute = AsyncMock(return_value=ActorReply(text=json.dumps(response)))
    return mock


def _idle_response(npc_name: str = _GUARD) -> dict:
    return {"action": f"{npc_name} continues watching the crowd.", "type": "IDLE", "target": None}


def _attack_response(target: str = "player") -> dict:
    return {"action": "The guard draws his sword and lunges!", "type": "ATTACK", "target": target}


def _move_response() -> dict:
    return {"action": "The merchant packs up and walks away.", "type": "MOVE", "target": None}


def _move_response_targeting(target: str) -> dict:
    return {"action": "The guard repositions toward the merchant.", "type": "MOVE", "target": target}


def _talk_response(target: str = "player") -> dict:
    return {"action": "The merchant calls out to you.", "type": "TALK", "target": target}


@allure.epic("NPC Interaction")
@allure.feature("NPC turn resolution")
class TestNPCTurnResolverInit:
    @allure.story("Resolver construction")
    @allure.title("NPCTurnResolver can be constructed with an empty actors dict and any game state")
    def test_creates_with_game_state_and_actors(self):
        gs = _make_gs()
        resolver = NPCTurnResolver(game_state=gs, actors={})
        assert resolver is not None


@allure.epic("NPC Interaction")
@allure.feature("NPC turn resolution")
class TestNPCTurnResolverEmptyScene:
    @allure.story("Empty scene")
    @allure.title("With no current_scene at all, NPC turn resolution returns an empty action list")
    @pytest.mark.asyncio
    async def test_no_scene_returns_empty(self):
        gs = _make_gs()
        gs.current_scene = None
        resolver = NPCTurnResolver(game_state=gs, actors={})
        actions = await resolver.resolve_npc_turns("Player looked around.")
        assert actions == []

    @allure.story("Empty scene")
    @allure.title("A scene with no NPCs present yields no NPC turn actions")
    @pytest.mark.asyncio
    async def test_no_npcs_returns_empty(self):
        gs = _make_gs()
        gs.current_scene = Scene(location_id="empty", description="Empty room.", npcs_present=[])
        resolver = NPCTurnResolver(game_state=gs, actors={})
        actions = await resolver.resolve_npc_turns("Player waited.")
        assert actions == []


@allure.epic("NPC Interaction")
@allure.feature("NPC turn resolution")
class TestNPCTurnResolverSingleNPC:
    @allure.story("Action parsing")
    @allure.title("A single NPC returning an IDLE JSON turn yields one action with no contest roll")
    @pytest.mark.asyncio
    async def test_single_npc_idle_action(self):
        gs = _make_gs()
        npc = _make_npc(_NPC_UUID_A, _GUARD)
        gs.npcs[_NPC_UUID_A] = npc
        gs.current_scene = _make_scene(_NPC_UUID_A)

        actor = _make_actor(_idle_response())
        resolver = NPCTurnResolver(game_state=gs, actors={_NPC_UUID_A: actor})

        actions = await resolver.resolve_npc_turns("Player waited.")

        assert len(actions) == 1
        assert actions[0].npc_uuid == _NPC_UUID_A
        assert actions[0].npc_name == _GUARD
        assert actions[0].action_type == "IDLE"
        assert actions[0].contest_roll is None

    @allure.story("Action parsing")
    @allure.title("Every resolved NPC turn populates a non-empty action_description string")
    @pytest.mark.asyncio
    async def test_npc_action_has_description(self):
        gs = _make_gs()
        npc = _make_npc(_NPC_UUID_A, _GUARD)
        gs.npcs[_NPC_UUID_A] = npc
        gs.current_scene = _make_scene(_NPC_UUID_A)

        actor = _make_actor(_idle_response())
        resolver = NPCTurnResolver(game_state=gs, actors={_NPC_UUID_A: actor})

        actions = await resolver.resolve_npc_turns("Player waited.")
        assert len(actions[0].action_description) > 0


@allure.epic("NPC Interaction")
@allure.feature("NPC turn resolution")
class TestNPCTurnResolverSkipsIncapacitated:
    @allure.story("Incapacitation")
    @allure.title("An unconscious NPC is skipped entirely and its actor is never called")
    @pytest.mark.asyncio
    async def test_unconscious_npc_skipped(self):
        gs = _make_gs()
        npc = _make_npc(_NPC_UUID_A, _GUARD, status="unconscious")
        gs.npcs[_NPC_UUID_A] = npc
        gs.current_scene = _make_scene(_NPC_UUID_A)

        actor = _make_actor(_idle_response())
        resolver = NPCTurnResolver(game_state=gs, actors={_NPC_UUID_A: actor})

        actions = await resolver.resolve_npc_turns("Player waited.")
        assert actions == []
        actor.execute.assert_not_called()

    @allure.story("Incapacitation")
    @allure.title("An NPC with physical_status 'dead' produces no turn action")
    @pytest.mark.asyncio
    async def test_dead_npc_skipped(self):
        gs = _make_gs()
        npc = _make_npc(_NPC_UUID_A, _GUARD, status="dead")
        gs.npcs[_NPC_UUID_A] = npc
        gs.current_scene = _make_scene(_NPC_UUID_A)

        actor = _make_actor(_idle_response())
        resolver = NPCTurnResolver(game_state=gs, actors={_NPC_UUID_A: actor})

        actions = await resolver.resolve_npc_turns("Player waited.")
        assert actions == []


@allure.epic("NPC Interaction")
@allure.feature("NPC turn resolution")
class TestNPCTurnResolverMultipleNPCs:
    @allure.story("Concurrent resolution")
    @allure.title("Multiple NPCs in a scene all resolve their turns in parallel and all appear in the result")
    @pytest.mark.asyncio
    async def test_multiple_npcs_resolve_simultaneously(self):
        gs = _make_gs()
        npc_a = _make_npc(_NPC_UUID_A, _GUARD)
        npc_b = _make_npc(_NPC_UUID_B, _MERCHANT)
        gs.npcs[_NPC_UUID_A] = npc_a
        gs.npcs[_NPC_UUID_B] = npc_b
        gs.current_scene = _make_scene(_NPC_UUID_A, _NPC_UUID_B)

        actor_a = _make_actor(_idle_response(_GUARD))
        actor_b = _make_actor(_talk_response())
        resolver = NPCTurnResolver(
            game_state=gs,
            actors={_NPC_UUID_A: actor_a, _NPC_UUID_B: actor_b},
        )

        actions = await resolver.resolve_npc_turns("Player explored.")

        assert len(actions) == 2
        names = {a.npc_name for a in actions}
        assert _GUARD in names
        assert _MERCHANT in names


@allure.epic("NPC Interaction")
@allure.feature("NPC turn resolution")
class TestNPCTurnContestAgainstPlayer:
    @allure.story("Target selection")
    @allure.title("An NPC ATTACK turn targeting the player generates a COMBAT contest roll on that action")
    @pytest.mark.asyncio
    async def test_attack_player_generates_contest(self):
        gs = _make_gs()
        npc = _make_npc(_NPC_UUID_A, _GUARD, combat_skill=5)
        gs.npcs[_NPC_UUID_A] = npc
        gs.current_scene = _make_scene(_NPC_UUID_A)

        actor = _make_actor(_attack_response("player"))
        resolver = NPCTurnResolver(game_state=gs, actors={_NPC_UUID_A: actor})

        actions = await resolver.resolve_npc_turns("Player insulted the guard.")

        assert len(actions) == 1
        assert actions[0].contest_roll is not None
        assert actions[0].contest_roll.contest_type == ContestType.COMBAT


@allure.epic("NPC Interaction")
@allure.feature("NPC turn resolution")
class TestNPCTurnContestNPCvsNPC:
    @allure.story("Target selection")
    @allure.title("An NPC attacking another NPC generates a COMBAT contest roll between the two NPCs")
    @pytest.mark.asyncio
    async def test_npc_attacks_other_npc_generates_contest(self):
        gs = _make_gs()
        npc_a = _make_npc(_NPC_UUID_A, _GUARD, combat_skill=5)
        npc_b = _make_npc(_NPC_UUID_B, _MERCHANT, combat_skill=2)
        gs.npcs[_NPC_UUID_A] = npc_a
        gs.npcs[_NPC_UUID_B] = npc_b
        gs.current_scene = _make_scene(_NPC_UUID_A, _NPC_UUID_B)

        actor_a = _make_actor(_attack_response(_MERCHANT))
        actor_b = _make_actor(_idle_response(_MERCHANT))
        resolver = NPCTurnResolver(
            game_state=gs,
            actors={_NPC_UUID_A: actor_a, _NPC_UUID_B: actor_b},
        )

        actions = await resolver.resolve_npc_turns("Player watched.")

        guard_action = next(a for a in actions if a.npc_name == _GUARD)
        assert guard_action.contest_roll is not None
        assert guard_action.contest_roll.contest_type == ContestType.COMBAT


@allure.epic("NPC Interaction")
@allure.feature("NPC turn resolution")
class TestNPCTurnSceneMutation:
    @allure.story("Scene mutation")
    @allure.title("An NPC MOVE turn removes the NPC from the current scene's npcs_present list")
    @pytest.mark.asyncio
    async def test_move_action_removes_npc_from_scene(self):
        gs = _make_gs()
        npc = _make_npc(_NPC_UUID_A, _MERCHANT)
        gs.npcs[_NPC_UUID_A] = npc
        gs.current_scene = _make_scene(_NPC_UUID_A)

        actor = _make_actor(_move_response())
        resolver = NPCTurnResolver(game_state=gs, actors={_NPC_UUID_A: actor})

        actions = await resolver.resolve_npc_turns("Player waited.")

        assert len(actions) == 1
        assert actions[0].action_type == "MOVE"
        scene_uuids = [snpc.uuid for snpc in gs.current_scene.npcs_present]
        assert _NPC_UUID_A not in scene_uuids

    @allure.story("Scene mutation")
    @allure.title("A MOVE targeting a co-located NPC name is repositioning, not departure — NPC stays in scene")
    @pytest.mark.asyncio
    async def test_move_targeting_scene_npc_keeps_npc_in_scene(self):
        gs = _make_gs()
        guard = _make_npc(_NPC_UUID_A, _GUARD)
        merchant = _make_npc(_NPC_UUID_B, _MERCHANT)
        gs.npcs[_NPC_UUID_A] = guard
        gs.npcs[_NPC_UUID_B] = merchant
        gs.current_scene = _make_scene(_NPC_UUID_A, _NPC_UUID_B)

        actor_a = _make_actor(_move_response_targeting(_MERCHANT))
        actor_b = _make_actor(_idle_response(_MERCHANT))
        resolver = NPCTurnResolver(
            game_state=gs,
            actors={_NPC_UUID_A: actor_a, _NPC_UUID_B: actor_b},
        )

        await resolver.resolve_npc_turns("Player waited.")

        scene_uuids = [snpc.uuid for snpc in gs.current_scene.npcs_present]
        assert _NPC_UUID_A in scene_uuids

    @allure.story("Scene mutation")
    @allure.title("MOVE targeting co-located NPC with different case still treats it as repositioning")
    @pytest.mark.asyncio
    async def test_move_targeting_scene_npc_case_insensitive(self):
        gs = _make_gs()
        guard = _make_npc(_NPC_UUID_A, _GUARD)
        merchant = _make_npc(_NPC_UUID_B, _MERCHANT)
        gs.npcs[_NPC_UUID_A] = guard
        gs.npcs[_NPC_UUID_B] = merchant
        gs.current_scene = _make_scene(_NPC_UUID_A, _NPC_UUID_B)

        actor_a = _make_actor(_move_response_targeting(_MERCHANT.lower()))
        actor_b = _make_actor(_idle_response(_MERCHANT))
        resolver = NPCTurnResolver(
            game_state=gs,
            actors={_NPC_UUID_A: actor_a, _NPC_UUID_B: actor_b},
        )

        await resolver.resolve_npc_turns("Player waited.")

        scene_uuids = [snpc.uuid for snpc in gs.current_scene.npcs_present]
        assert _NPC_UUID_A in scene_uuids

    @allure.story("Scene mutation")
    @allure.title("MOVE targeting a registered NPC not present in this scene is treated as departure")
    @pytest.mark.asyncio
    async def test_move_targeting_absent_registered_npc_evicts(self):
        gs = _make_gs()
        guard = _make_npc(_NPC_UUID_A, _GUARD)
        absent = _make_npc("npc-absent", "Caesar")
        gs.npcs[_NPC_UUID_A] = guard
        gs.npcs["npc-absent"] = absent
        gs.current_scene = _make_scene(_NPC_UUID_A)

        actor_a = _make_actor(_move_response_targeting("Caesar"))
        resolver = NPCTurnResolver(game_state=gs, actors={_NPC_UUID_A: actor_a})

        await resolver.resolve_npc_turns("Player waited.")

        scene_uuids = [snpc.uuid for snpc in gs.current_scene.npcs_present]
        assert _NPC_UUID_A not in scene_uuids

    @allure.story("Scene mutation")
    @allure.title("MOVE targeting the player sentinel is treated as repositioning, not departure")
    @pytest.mark.asyncio
    async def test_move_targeting_player_keeps_npc_in_scene(self):
        gs = _make_gs()
        guard = _make_npc(_NPC_UUID_A, _GUARD)
        gs.npcs[_NPC_UUID_A] = guard
        gs.current_scene = _make_scene(_NPC_UUID_A)

        actor = _make_actor(_move_response_targeting("player"))
        resolver = NPCTurnResolver(game_state=gs, actors={_NPC_UUID_A: actor})

        await resolver.resolve_npc_turns("Player waited.")

        scene_uuids = [snpc.uuid for snpc in gs.current_scene.npcs_present]
        assert _NPC_UUID_A in scene_uuids


@allure.epic("NPC Interaction")
@allure.feature("NPC turn resolution")
class TestNPCTurnResolverErrorHandling:
    @allure.story("Error handling")
    @allure.title("An LLM failure for one NPC does not prevent other NPCs from completing their turns")
    @pytest.mark.asyncio
    async def test_one_npc_failure_does_not_kill_others(self):
        gs = _make_gs()
        guard = _make_npc(_NPC_UUID_A, _GUARD)
        merchant = _make_npc(_NPC_UUID_B, _MERCHANT)
        gs.npcs[_NPC_UUID_A] = guard
        gs.npcs[_NPC_UUID_B] = merchant
        gs.current_scene = _make_scene(_NPC_UUID_A, _NPC_UUID_B)

        failing_actor = AsyncMock()
        failing_actor.execute = AsyncMock(side_effect=RuntimeError("LLM timeout"))
        ok_actor = _make_actor(_idle_response(_MERCHANT))

        resolver = NPCTurnResolver(
            game_state=gs,
            actors={_NPC_UUID_A: failing_actor, _NPC_UUID_B: ok_actor},
        )

        actions = await resolver.resolve_npc_turns("Player waited.")

        assert len(actions) == 1
        assert actions[0].npc_name == _MERCHANT


@allure.epic("NPC Interaction")
@allure.feature("NPC autonomous turn — opportunity window")
def _place_both(gs: GameState, actor: NPCCard, target: NPCCard) -> None:
    gs.npcs[actor.uuid] = actor
    gs.npcs[target.uuid] = target
    gs.current_scene = _make_scene(actor.uuid, target.uuid)


def _plot_knowledge(gs: GameState, npc_uuid: str, text: str) -> None:
    plot_node = KnowledgeNode(
        text=text,
        scope=KnowledgeScope.LOCAL,
        source=KnowledgeSource.PERSONAL_EXPERIENCE,
        canon=CanonSource.SESSION,
    )
    gs.knowledge_graph.add_node(plot_node)
    gs.knowledge_graph.add_edge(npc_uuid, plot_node.uuid, EdgeType.WITNESSED)


@allure.epic("NPC Interaction")
@allure.feature("NPC autonomous turn — opportunity window")
class TestBuildTurnPromptOpportunityWindow:
    """``_build_turn_prompt`` surfaces an OPPORTUNITY clause when the scene
    puts a hostile-labelled target (via relationship) or a violence-flavoured
    knowledge fact about a co-located NPC within reach, and drops the baseline
    "most turns are routine" nudge so the two do not contradict each other.
    """

    @allure.story("Opportunity window")
    @allure.title("Co-located hostile relationship fires the opportunity clause and drops the routine nudge")
    def test_hostile_relationship_fires_clause(self):
        gs = _make_gs()
        brutus = _make_npc(_NPC_UUID_A, "Brutus")
        marcus = _make_npc(_NPC_UUID_B, "Marcus")
        brutus.relationships[_NPC_UUID_B] = "murderous_enemy"
        _place_both(gs, brutus, marcus)

        prompt = npc_turn_mod._build_turn_prompt(brutus, "Player waits.", gs)

        assert "OPPORTUNITY:" in prompt
        assert "Most turns are routine" not in prompt

    @allure.story("Opportunity window")
    @allure.title("Peaceful peer with no hostile signals sees the baseline routine nudge")
    def test_peaceful_peer_keeps_routine_nudge(self):
        gs = _make_gs()
        cook = _make_npc(_NPC_UUID_A, "Cook")
        carpenter = _make_npc(_NPC_UUID_B, "Carpenter")
        cook.relationships[_NPC_UUID_B] = "acquaintance"
        _place_both(gs, cook, carpenter)

        prompt = npc_turn_mod._build_turn_prompt(cook, "Player waits.", gs)

        assert "OPPORTUNITY:" not in prompt
        assert "Most turns are routine" in prompt

    @allure.story("Opportunity window")
    @allure.title("Violent knowledge fact naming a co-located NPC fires the clause without any relationship")
    def test_knowledge_only_gate_fires_clause(self):
        gs = _make_gs()
        brutus = _make_npc(_NPC_UUID_A, "Brutus")
        marcus = _make_npc(_NPC_UUID_B, "Marcus")
        _place_both(gs, brutus, marcus)
        _plot_knowledge(gs, brutus.uuid, "Brutus intends to kill Marcus today.")

        prompt = npc_turn_mod._build_turn_prompt(brutus, "Player waits.", gs)

        assert "OPPORTUNITY:" in prompt
        assert "Most turns are routine" not in prompt
        assert "Marcus" in prompt

    @allure.story("Opportunity window")
    @allure.title("Violent knowledge naming an absent NPC does not fire the clause")
    def test_knowledge_about_absent_npc_does_not_fire(self):
        gs = _make_gs()
        brutus = _make_npc(_NPC_UUID_A, "Brutus")
        other_bystander = _make_npc(_NPC_UUID_B, "Titus")
        absent = _make_npc("npc-absent", "Marcus")
        gs.npcs[absent.uuid] = absent
        _place_both(gs, brutus, other_bystander)
        _plot_knowledge(gs, brutus.uuid, "Brutus intends to kill Marcus today.")

        prompt = npc_turn_mod._build_turn_prompt(brutus, "Player waits.", gs)

        assert "OPPORTUNITY:" not in prompt
        assert "Most turns are routine" in prompt

    @allure.story("Opportunity window")
    @allure.title("Label containing 'kill' as a substring of 'skillful' does not fire on its own")
    def test_skillful_prefix_alone_does_not_fire(self):
        gs = _make_gs()
        apprentice = _make_npc(_NPC_UUID_A, "Apprentice")
        apothecary = _make_npc(_NPC_UUID_B, "Apothecary")
        apprentice.relationships[_NPC_UUID_B] = "skillful apprentice"
        _place_both(gs, apprentice, apothecary)
        _plot_knowledge(gs, apprentice.uuid, "The pharmacist Apothecary mixes salves all day.")

        prompt = npc_turn_mod._build_turn_prompt(apprentice, "Player waits.", gs)

        assert "OPPORTUNITY:" not in prompt
        assert "Most turns are routine" in prompt

    @allure.story("Opportunity window")
    @allure.title("Opportunity clause names the specific hostile co-located target")
    def test_opportunity_clause_names_target(self):
        gs = _make_gs()
        brutus = _make_npc(_NPC_UUID_A, "Brutus")
        marcus = _make_npc(_NPC_UUID_B, "Marcus")
        brutus.relationships[_NPC_UUID_B] = "murderous_enemy"
        _place_both(gs, brutus, marcus)

        prompt = npc_turn_mod._build_turn_prompt(brutus, "Player waits.", gs)

        assert "Marcus" in prompt

    @allure.story("Opportunity window")
    @allure.title("Genuine keyword fires even when the label also contains substring-only matches")
    def test_genuine_keyword_fires_alongside_false_positive_prefix(self):
        gs = _make_gs()
        apprentice = _make_npc(_NPC_UUID_A, "Apprentice")
        apothecary = _make_npc(_NPC_UUID_B, "Apothecary")
        # "skillful" contains "kill" but is word-boundary-rejected; "rival"
        # is a genuine keyword and must still fire alongside it.
        apprentice.relationships[_NPC_UUID_B] = "skillful rival apprentice"
        _place_both(gs, apprentice, apothecary)

        prompt = npc_turn_mod._build_turn_prompt(apprentice, "Player waits.", gs)

        assert "OPPORTUNITY:" in prompt


@allure.epic("NPC Interaction")
@allure.feature("NPC autonomous turn — opportunity window")
class TestBuildTurnPromptOpportunityWindowIntegration:
    """End-to-end check that the OPPORTUNITY clause actually reaches the
    Actor's LLM call. ``_build_turn_prompt`` output becomes the Actor's
    ``input_data`` in ``NPCTurnResolver._resolve_single_npc``; if that
    plumbing breaks, the unit tests above would still pass but the LLM
    would never see the cue.
    """

    @allure.story("Opportunity window")
    @allure.title("Opportunity clause reaches Actor.execute input_data via the resolver path")
    @pytest.mark.asyncio
    async def test_opportunity_clause_flows_into_actor_input(self):
        gs = _make_gs()
        brutus = _make_npc(_NPC_UUID_A, "Brutus")
        marcus = _make_npc(_NPC_UUID_B, "Marcus")
        brutus.relationships[_NPC_UUID_B] = "murderous_enemy"
        _place_both(gs, brutus, marcus)

        brutus_actor = _make_actor(_idle_response("Brutus"))
        marcus_actor = _make_actor(_idle_response(_MERCHANT))
        resolver = NPCTurnResolver(
            game_state=gs,
            actors={_NPC_UUID_A: brutus_actor, _NPC_UUID_B: marcus_actor},
        )

        await resolver.resolve_npc_turns("Player waits.")

        brutus_input = brutus_actor.execute.await_args.kwargs["input_data"]
        assert "OPPORTUNITY:" in brutus_input
        assert "Most turns are routine" not in brutus_input
        brutus_context = brutus_actor.execute.await_args.kwargs["context"]
        assert brutus_context["is_npc_turn"] is True

        marcus_input = marcus_actor.execute.await_args.kwargs["input_data"]
        assert "OPPORTUNITY:" not in marcus_input


@allure.epic("NPC Interaction")
@allure.feature("NPC turn resolution")
class TestNPCActionDataclass:
    @allure.story("NPCAction dataclass")
    @allure.title("NPCAction dataclass stores uuid, name, description, type, target, and optional contest roll")
    def test_npc_action_fields(self):
        action = NPCAction(
            npc_uuid="u1",
            npc_name="Guard",
            action_description="Stands guard.",
            action_type="IDLE",
            target=None,
            contest_roll=None,
        )
        assert action.npc_uuid == "u1"
        assert action.npc_name == "Guard"
        assert action.action_description == "Stands guard."
        assert action.action_type == "IDLE"
        assert action.target is None
        assert action.contest_roll is None
