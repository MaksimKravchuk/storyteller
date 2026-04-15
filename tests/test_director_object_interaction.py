"""Tests for cast.director_object_interaction — KER-13 regression.

These cover the INTERACT-with-object path that gives actions like
"break the window" a real handler: LLM-backed narration, a persistent
``scene_state`` delta in the knowledge graph, and witness memories
for every initialised scene NPC. Also includes the cross-rebuild
regression that asserts a delta survives a MOVE away + MOVE back
cycle and reaches the Scene Builder's prompt on the second visit.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import allure
import pytest

from cast import director_object_interaction as doi_mod, item_generator as ig_mod, scene_builder as sb_mod
from cast.schemas import item_response as item_resp, scene_response as scene_resp
from knowledge.memory import MemoryManager
from knowledge.query import KnowledgeQueryEngine
from knowledge.scene_state import SCENE_STATE_TAG, query_scene_deltas
from llm.message import LLMResponse
from models import location as location_mod, scene as scene_mod
from tests.director_helpers import make_game_state, setup_npc

_SEND_JSON = "_send_json"
_NPC_UUID = "npc-bystander"


def _stub_item_generator(response: item_resp.ObjectInteractionResponse) -> ig_mod.ItemGenerator:
    """Build a real ItemGenerator whose LLM call returns the given response."""
    gen = ig_mod.ItemGenerator(llm_client=MagicMock())
    gen._send_json = AsyncMock(return_value=response)  # type: ignore[method-assign]
    return gen


def _memory_manager_with_stub_llm(graph) -> MemoryManager:
    memory_llm = AsyncMock()
    memory_llm.send_message = AsyncMock(
        return_value=LLMResponse(body="unused summary", model="stub", usage={}),
    )
    return MemoryManager(graph=graph, llm_client=memory_llm)


@allure.epic("Scene & Exploration")
@allure.feature("Object interaction persistence")
class TestApplyObjectInteractions:
    @allure.story("Narration + delta")
    @allure.title("apply_object_interactions returns narration strings and writes a scene_state delta to the graph")
    @pytest.mark.asyncio
    async def test_persists_delta_and_returns_narration(self):
        gs = make_game_state()
        gs.current_scene = scene_mod.Scene(
            location_id="tavern",
            description="The Rusty Anchor, dim and smoky.",
            npcs_present=[],
        )
        item_gen = _stub_item_generator(
            item_resp.ObjectInteractionResponse(
                narration="Glass shatters with a sharp crack.",
                delta="The front window is broken.",
            ),
        )
        memory_manager = _memory_manager_with_stub_llm(gs.knowledge_graph)

        result = await doi_mod.apply_object_interactions(
            item_gen,
            ["window"],
            "break the window",
            gs,
            memory_manager,
        )

        assert result.narrations == ["Glass shatters with a sharp crack."]
        assert result.deltas == ["The front window is broken."]
        deltas = query_scene_deltas(gs.knowledge_graph, "tavern")
        assert len(deltas) == 1
        assert deltas[0].text == "The front window is broken."
        assert SCENE_STATE_TAG in deltas[0].tags

    @allure.story("Witness memories")
    @allure.title("apply_object_interactions emits a personal memory for every initialised scene NPC")
    @pytest.mark.asyncio
    async def test_emits_witness_memories_for_scene_npcs(self):
        gs = make_game_state()
        setup_npc(gs, _NPC_UUID, name="Livia", occupation="innkeeper")
        gs.knowledge_graph.register_actor_node(_NPC_UUID, label="Livia (innkeeper)")
        gs.current_scene = scene_mod.Scene(
            location_id="tavern",
            description="The Rusty Anchor.",
            npcs_present=[scene_mod.SceneNPC(role="innkeeper", uuid=_NPC_UUID)],
        )
        item_gen = _stub_item_generator(
            item_resp.ObjectInteractionResponse(
                narration="Shards clatter to the boards.",
                delta="The front window is broken.",
            ),
        )
        memory_manager = _memory_manager_with_stub_llm(gs.knowledge_graph)

        await doi_mod.apply_object_interactions(
            item_gen,
            ["window"],
            "break the window",
            gs,
            memory_manager,
        )

        memories = KnowledgeQueryEngine(gs.knowledge_graph).get_memories_about(_NPC_UUID)
        assert len(memories) == 1
        assert "window is broken" in memories[0].text.lower()

    @allure.story("Empty delta")
    @allure.title("apply_object_interactions skips the graph write when the LLM returns an empty delta")
    @pytest.mark.asyncio
    async def test_empty_delta_skips_graph_write(self):
        gs = make_game_state()
        setup_npc(gs, _NPC_UUID, name="Livia", occupation="innkeeper")
        gs.knowledge_graph.register_actor_node(_NPC_UUID, label="Livia (innkeeper)")
        gs.current_scene = scene_mod.Scene(
            location_id="tavern",
            description="The Rusty Anchor.",
            npcs_present=[scene_mod.SceneNPC(role="innkeeper", uuid=_NPC_UUID)],
        )
        item_gen = _stub_item_generator(
            item_resp.ObjectInteractionResponse(
                narration="You bump into the wall; nothing gives.",
                delta="",
            ),
        )
        memory_manager = _memory_manager_with_stub_llm(gs.knowledge_graph)

        result = await doi_mod.apply_object_interactions(
            item_gen,
            ["wall"],
            "shove the wall",
            gs,
            memory_manager,
        )

        assert result.narrations == ["You bump into the wall; nothing gives."]
        assert result.deltas == [""]
        assert query_scene_deltas(gs.knowledge_graph, "tavern") == []
        # No delta → no witness memory either. The bystander's graph node
        # exists but has no PERSONAL_EXPERIENCE edges.
        assert KnowledgeQueryEngine(gs.knowledge_graph).get_memories_about(_NPC_UUID) == []

    @allure.story("No item generator wired")
    @allure.title("apply_object_interactions returns early when the cast has no item_generator")
    @pytest.mark.asyncio
    async def test_no_item_generator_returns_empty(self):
        gs = make_game_state()
        memory_manager = _memory_manager_with_stub_llm(gs.knowledge_graph)
        result = await doi_mod.apply_object_interactions(None, ["window"], "break the window", gs, memory_manager)
        assert result.narrations == []
        assert result.deltas == []

    @allure.story("Empty target list")
    @allure.title("apply_object_interactions returns early when the target list is empty")
    @pytest.mark.asyncio
    async def test_empty_targets_returns_empty(self):
        gs = make_game_state()
        item_gen = _stub_item_generator(item_resp.ObjectInteractionResponse())
        memory_manager = _memory_manager_with_stub_llm(gs.knowledge_graph)
        result = await doi_mod.apply_object_interactions(item_gen, [], "break everything", gs, memory_manager)
        assert result.narrations == []
        assert result.deltas == []
        item_gen._send_json.assert_not_awaited()  # type: ignore[attr-defined]

    @allure.story("Uninitialised scene stubs")
    @allure.title("apply_object_interactions does not emit witness memories for uninitialised scene NPC stubs")
    @pytest.mark.asyncio
    async def test_uninitialised_scene_stub_skipped(self):
        gs = make_game_state()
        gs.current_scene = scene_mod.Scene(
            location_id="tavern",
            description="The Rusty Anchor.",
            npcs_present=[scene_mod.SceneNPC(role="beggar")],  # No uuid, no card.
        )
        item_gen = _stub_item_generator(
            item_resp.ObjectInteractionResponse(
                narration="Shards clatter to the boards.",
                delta="The front window is broken.",
            ),
        )
        memory_manager = _memory_manager_with_stub_llm(gs.knowledge_graph)
        nodes_before = len(gs.knowledge_graph.digraph.nodes)

        await doi_mod.apply_object_interactions(item_gen, ["window"], "break the window", gs, memory_manager)

        nodes_after = len(gs.knowledge_graph.digraph.nodes)
        # Exactly one new node: the scene_state delta. No stray personal
        # memories for the uninitialised beggar stub.
        assert nodes_after - nodes_before == 1


@allure.epic("Scene & Exploration")
@allure.feature("Object interaction persistence")
class TestSceneBuilderDeltaInjection:
    @allure.story("Cross-rebuild persistence")
    @allure.title(
        "A scene_state delta written at location A reaches the Scene Builder prompt "
        "when the player later returns to A (KER-13 regression)",
    )
    @pytest.mark.asyncio
    async def test_delta_survives_move_away_and_return(self):
        """KER-13 primary regression.

        Phase 1: INTERACT "break the window" at the tavern → the
        object-interaction handler writes a ``scene_state`` delta.
        Phase 2: player MOVEs to a different location → the Scene
        Builder rebuilds the scene for somewhere else.
        Phase 3: player MOVEs back to the tavern → the Scene Builder
        rebuilds the tavern scene. The delta must still be in the graph
        *and* must reach the SceneBuilder's system prompt via the
        ``persistent_world_changes`` section so the LLM is instructed
        not to regenerate a pristine window.
        """
        gs = make_game_state()
        gs.current_scene = scene_mod.Scene(
            location_id="tavern",
            description="The Rusty Anchor.",
            npcs_present=[],
        )

        # --- Phase 1: break the window at the tavern ---
        item_gen = _stub_item_generator(
            item_resp.ObjectInteractionResponse(
                narration="Glass shatters with a sharp crack.",
                delta="The front window is broken.",
            ),
        )
        memory_manager = _memory_manager_with_stub_llm(gs.knowledge_graph)
        await doi_mod.apply_object_interactions(
            item_gen,
            ["window"],
            "break the window",
            gs,
            memory_manager,
        )

        # The delta is in the graph under the tavern location.
        deltas = query_scene_deltas(gs.knowledge_graph, "tavern")
        assert len(deltas) == 1

        # --- Phase 2: MOVE to the forum ---
        builder = sb_mod.SceneBuilder(llm_client=MagicMock())
        forum_response = scene_resp.SceneResponse(
            location_id="forum",
            description="A bustling Roman Forum.",
            npcs_present=[],
            points_of_interest=["fountain"],
        )
        with patch.object(builder, _SEND_JSON, new=AsyncMock(return_value=forum_response)):
            new_scene = await builder.act("walk to the forum", {"game_state": gs})
        gs.current_scene = new_scene

        # Delta must still be queryable after the move — the scene_state
        # node is tied to location_id, not the live current_scene.
        assert len(query_scene_deltas(gs.knowledge_graph, "tavern")) == 1

        # --- Phase 3: MOVE back to the tavern ---
        # Capture the system prompt the Scene Builder renders on the
        # second visit: it must contain the broken-window delta.
        tavern_response = scene_resp.SceneResponse(
            location_id="tavern",
            description="The Rusty Anchor — now with a shattered front window.",
            npcs_present=[],
            points_of_interest=["broken window"],
        )
        with patch.object(builder, _SEND_JSON, new=AsyncMock(return_value=tavern_response)):
            returned_scene = await builder.act("walk back to the tavern", {"game_state": gs})
        gs.current_scene = returned_scene

        rendered_system_prompt = builder._build_system_prompt()
        assert "The front window is broken." in rendered_system_prompt
        assert "tavern" in rendered_system_prompt
        # Sanity: the delta did not evaporate during the round-trip.
        assert len(query_scene_deltas(gs.knowledge_graph, "tavern")) == 1


@allure.epic("Scene & Exploration")
@allure.feature("Object interaction persistence")
class TestApplyObjectInteractionsDualSink:
    """KER-16 — ``_persist_delta`` must write the knowledge-graph delta
    and the typed ``Location.object_states`` entry in lockstep so the
    Narrator's ``Prior damage:`` line and the SceneBuilder's
    ``known_object_states`` block never disagree.
    """

    @allure.story("Dual-sink persistence")
    @allure.title("apply_object_interactions writes the delta into Location.object_states alongside the graph delta")
    @pytest.mark.asyncio
    async def test_writes_typed_channel_and_graph(self):
        gs = make_game_state()
        gs.locations["tavern"] = location_mod.Location(uuid="tavern", name="Rusty Anchor")
        gs.current_scene = scene_mod.Scene(location_id="tavern", description="The Rusty Anchor.")
        item_gen = _stub_item_generator(
            item_resp.ObjectInteractionResponse(
                narration="Glass shatters.",
                delta="The front window is broken.",
            ),
        )
        memory_manager = _memory_manager_with_stub_llm(gs.knowledge_graph)

        await doi_mod.apply_object_interactions(
            item_gen,
            ["window"],
            "break the window",
            gs,
            memory_manager,
        )

        assert gs.locations["tavern"].object_states == {"window": "The front window is broken."}
        assert len(query_scene_deltas(gs.knowledge_graph, "tavern")) == 1

    @allure.story("Dual-sink persistence")
    @allure.title("apply_object_interactions normalizes paraphrased object keys to a single object_states slot")
    @pytest.mark.asyncio
    async def test_normalizes_paraphrased_keys(self):
        gs = make_game_state()
        gs.locations["tavern"] = location_mod.Location(uuid="tavern", name="Rusty Anchor")
        gs.current_scene = scene_mod.Scene(location_id="tavern", description="The Rusty Anchor.")
        item_gen = _stub_item_generator(
            item_resp.ObjectInteractionResponse(
                narration="You hit the shutter.",
                delta="The wooden shutter is splintered.",
            ),
        )
        memory_manager = _memory_manager_with_stub_llm(gs.knowledge_graph)

        await doi_mod.apply_object_interactions(
            item_gen,
            ["Wooden_Shutter"],
            "break the shutter",
            gs,
            memory_manager,
        )

        assert gs.locations["tavern"].object_states == {"wooden shutter": "The wooden shutter is splintered."}

    @allure.story("Dual-sink persistence")
    @allure.title("apply_object_interactions pairs multi-target deltas with their object keys in order")
    @pytest.mark.asyncio
    async def test_multi_target_pairing(self):
        gs = make_game_state()
        gs.locations["tavern"] = location_mod.Location(uuid="tavern", name="Rusty Anchor")
        gs.current_scene = scene_mod.Scene(location_id="tavern", description="The Rusty Anchor.")
        gen = ig_mod.ItemGenerator(llm_client=MagicMock())
        responses = [
            item_resp.ObjectInteractionResponse(
                narration="Glass shatters.",
                delta="The window is broken.",
            ),
            item_resp.ObjectInteractionResponse(
                narration="The door splinters.",
                delta="The door is splintered.",
            ),
        ]
        gen._send_json = AsyncMock(side_effect=responses)  # type: ignore[method-assign]
        memory_manager = _memory_manager_with_stub_llm(gs.knowledge_graph)

        await doi_mod.apply_object_interactions(
            gen,
            ["window", "door"],
            "break the window and the door",
            gs,
            memory_manager,
        )

        assert gs.locations["tavern"].object_states == {
            "window": "The window is broken.",
            "door": "The door is splintered.",
        }

    @allure.story("Dual-sink persistence")
    @allure.title("apply_object_interactions skips both sinks when the resolved object_key is empty")
    @pytest.mark.asyncio
    async def test_empty_object_key_skips_both_sinks(self):
        gs = make_game_state()
        gs.locations["tavern"] = location_mod.Location(uuid="tavern", name="Rusty Anchor")
        gs.current_scene = scene_mod.Scene(location_id="tavern", description="The Rusty Anchor.")
        item_gen = _stub_item_generator(
            item_resp.ObjectInteractionResponse(narration="Nothing happens.", delta="Wall is cracked."),
        )
        memory_manager = _memory_manager_with_stub_llm(gs.knowledge_graph)

        await doi_mod.apply_object_interactions(
            item_gen,
            [""],
            "vague action",
            gs,
            memory_manager,
        )

        assert gs.locations["tavern"].object_states == {}
        assert query_scene_deltas(gs.knowledge_graph, "tavern") == []

    @allure.story("Dual-sink persistence")
    @allure.title("apply_object_interactions keeps the graph write loud when the scene's location is unregistered")
    @pytest.mark.asyncio
    async def test_missing_location_logs_but_writes_graph(self):
        gs = make_game_state()
        gs.current_scene = scene_mod.Scene(location_id="ghost", description="Nowhere.")
        item_gen = _stub_item_generator(
            item_resp.ObjectInteractionResponse(
                narration="The wall cracks.",
                delta="The wall is cracked.",
            ),
        )
        memory_manager = _memory_manager_with_stub_llm(gs.knowledge_graph)

        await doi_mod.apply_object_interactions(
            item_gen,
            ["wall"],
            "crack the wall",
            gs,
            memory_manager,
        )

        # Graph write still fires — the dangling location only blocks the typed channel.
        assert len(query_scene_deltas(gs.knowledge_graph, "ghost")) == 1
        assert "ghost" not in gs.locations
