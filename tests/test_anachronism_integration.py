"""Integration tests for the anachronism feature.

Exercises the consumer-side seams the issue (#186) calls out — the
classifier verdict reaching both the Actor input and the Narrator's
``DialogueEntry`` — plus the once-per-turn caching invariant and the
end-to-end memory write that closes the familiarity loop.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import allure
import pytest

from cast import anachronism as anachronism_mod, director_dialogue as dlg_mod
from cast.schemas import anachronism as schema_mod
from knowledge import graph as graph_mod, memory as memory_mod, node as _node, salience as salience_presets
from llm.message import LLMResponse
from models import game_state as gs_mod, npc_card as npc_card_mod, scene as scene_mod, setting as setting_mod
from tests import actor_helpers
from tests._uuid_helpers import make_uuid

AnachronismClassifier = anachronism_mod.AnachronismClassifier
TurnAnachronismContext = anachronism_mod.TurnAnachronismContext
DialogueHandler = dlg_mod.DialogueHandler
AnachronismClassification = schema_mod.AnachronismClassification
KnowledgeGraph = graph_mod.KnowledgeGraph
MemoryManager = memory_mod.MemoryManager
KnowledgeSource = _node.KnowledgeSource
GameState = gs_mod.GameState
PlayerState = gs_mod.PlayerState
NPCCard = npc_card_mod.NPCCard
Scene = scene_mod.Scene
SceneNPC = scene_mod.SceneNPC
Setting = setting_mod.Setting

pytestmark = [
    allure.epic("World & Setting"),
    allure.feature("Anachronism awareness"),
]

_FORUM = make_uuid("forum-int")
_MARCUS = make_uuid("npc-marcus-int")
_CASSIA = make_uuid("npc-cassia-int")
_GAIUS = make_uuid("npc-gaius-int")
_FLAME = "light_without_flame"
_PHOTO = "image_capture"
_REWRITE = "the stranger raised a tablet that lit by itself"
_FRAMING_HINT = f"The NPC perceives this as: {_REWRITE}"


def _make_setting() -> Setting:
    return Setting(
        name="Ancient Rome",
        time_period="1st century AD",
        region="Italy",
        summary="The Roman Empire.",
        technologies=["oil lamps", "iron tools"],
        social_structure="Republic.",
    )


def _make_state() -> GameState:
    graph = KnowledgeGraph()
    state = GameState(
        setting=_make_setting(),
        knowledge_graph=graph,
        player=PlayerState(name="Traveller", origin_era="21st century earth"),
    )
    state.player.location_id = _FORUM
    return state


def _add_npc(state: GameState, uuid, name: str, education: int = 5) -> NPCCard:
    npc = NPCCard(name=name, occupation="legionary", attributes={"education": education})
    npc.uuid = uuid
    npc.location_id = _FORUM
    state.npcs[uuid] = npc
    state.knowledge_graph.register_actor_node(uuid, label=name)
    return npc


def _stub_classifier(verdict: AnachronismClassification) -> AnachronismClassifier:
    classifier = AnachronismClassifier(llm_client=AsyncMock())
    classifier.classify = AsyncMock(return_value=verdict)  # type: ignore[method-assign]
    return classifier


def _make_memory_manager(graph: KnowledgeGraph) -> MemoryManager:
    """Build a real MemoryManager backed by a no-op LLM stub.

    The summariser only writes a node when its LLM returns non-empty text;
    handing it an empty string keeps the test focused on the anachronism
    memory write that ``handle_dialogue`` adds at the end of the turn.
    """
    llm = AsyncMock()
    llm.send_message = AsyncMock(return_value=LLMResponse(body="", model="stub", usage={}))
    return MemoryManager(graph=graph, llm_client=llm)


def _scene_with(npcs: list[tuple[NPCCard, str]]) -> Scene:
    return Scene(
        location_id=_FORUM,
        description="The bustling Roman forum.",
        npcs_present=[SceneNPC(role=role, uuid=npc.uuid) for npc, role in npcs],
    )


@allure.story("Once per turn")
class TestClassifierFiresOnce:
    @allure.title("Classifier runs exactly once for a 3-NPC scene")
    @pytest.mark.asyncio
    async def test_three_npcs_one_classifier_call(self):
        state = _make_state()
        marcus = _add_npc(state, _MARCUS, "Marcus")
        cassia = _add_npc(state, _CASSIA, "Cassia")
        gaius = _add_npc(state, _GAIUS, "Gaius")
        state.current_scene = _scene_with([(marcus, "marcus"), (cassia, "cassia"), (gaius, "gaius")])

        classifier = _stub_classifier(
            AnachronismClassification(
                strangeness_score=6,
                unfamiliar_concepts=[_FLAME],
                perceived_rewrite=_REWRITE,
            ),
        )
        ctx = TurnAnachronismContext.create_for(classifier, state, "raise the glowing tablet")

        actors = {npc.uuid: actor_helpers.make_mock_actor(text="bewildered reply") for npc in (marcus, cassia, gaius)}
        handler = DialogueHandler(state, actors, _make_memory_manager(state.knowledge_graph))

        entries, _combat = await handler.handle_dialogue(
            "raise the glowing tablet",
            target_names=["Marcus", "Cassia", "Gaius"],
            anachronism_ctx=ctx,
        )

        classifier.classify.assert_awaited_once()  # type: ignore[attr-defined]
        assert len(entries) == 3


@allure.story("Consumer-side seams")
class TestPerceivedRewriteReachesBothSeams:
    @allure.title("perceived_rewrite reaches the Actor's input action_text")
    @pytest.mark.asyncio
    async def test_rewrite_reaches_actor_input(self):
        state = _make_state()
        marcus = _add_npc(state, _MARCUS, "Marcus")
        state.current_scene = _scene_with([(marcus, "marcus")])

        verdict = AnachronismClassification(
            strangeness_score=6,
            unfamiliar_concepts=[_FLAME],
            perceived_rewrite=_REWRITE,
        )
        classifier = _stub_classifier(verdict)
        ctx = TurnAnachronismContext.create_for(classifier, state, "raise the glowing tablet")

        actor = actor_helpers.make_mock_actor(text="reply")
        actors = {marcus.uuid: actor}
        handler = DialogueHandler(state, actors, _make_memory_manager(state.knowledge_graph))

        await handler.handle_dialogue(
            "raise the glowing tablet",
            target_names=["Marcus"],
            contest_info={"type": "intimidation", "target": "Marcus"},
            anachronism_ctx=ctx,
        )

        # Actor.execute was called exactly once; inspect what action_text reached it.
        actor.execute.assert_awaited_once()
        call_kwargs = actor.execute.await_args.kwargs
        action_text = call_kwargs["input_data"]
        assert _FRAMING_HINT in action_text

    @allure.title("perceived_rewrite reaches the DialogueEntry the Narrator reads")
    @pytest.mark.asyncio
    async def test_rewrite_reaches_dialogue_entry(self):
        state = _make_state()
        marcus = _add_npc(state, _MARCUS, "Marcus")
        state.current_scene = _scene_with([(marcus, "marcus")])

        verdict = AnachronismClassification(
            strangeness_score=6,
            unfamiliar_concepts=[_FLAME, _PHOTO],
            perceived_rewrite=_REWRITE,
        )
        classifier = _stub_classifier(verdict)
        ctx = TurnAnachronismContext.create_for(classifier, state, "raise the glowing tablet")

        actors = {marcus.uuid: actor_helpers.make_mock_actor(text="bewildered reply")}
        handler = DialogueHandler(state, actors, _make_memory_manager(state.knowledge_graph))

        entries, _combat = await handler.handle_dialogue(
            "raise the glowing tablet",
            target_names=["Marcus"],
            contest_info={"type": "intimidation", "target": "Marcus"},
            anachronism_ctx=ctx,
        )

        assert len(entries) == 1
        entry = entries[0]
        assert entry["perceived_rewrite"] == _REWRITE
        assert entry["unfamiliar_concepts"] == [_FLAME, _PHOTO]


@allure.story("Familiarity loop")
class TestEncounterMemoryClosesFamiliarityLoop:
    @allure.title("After one encounter the NPC's memories carry a tagged anachronism KnowledgeNode")
    @pytest.mark.asyncio
    async def test_first_encounter_persists_tagged_memory(self):
        state = _make_state()
        marcus = _add_npc(state, _MARCUS, "Marcus")
        state.current_scene = _scene_with([(marcus, "marcus")])

        verdict = AnachronismClassification(
            strangeness_score=6,
            unfamiliar_concepts=[_FLAME],
            perceived_rewrite=_REWRITE,
        )
        classifier = _stub_classifier(verdict)
        ctx = TurnAnachronismContext.create_for(classifier, state, "raise the glowing tablet")

        actors = {marcus.uuid: actor_helpers.make_mock_actor(text="reply")}
        handler = DialogueHandler(state, actors, _make_memory_manager(state.knowledge_graph))

        await handler.handle_dialogue(
            "raise the glowing tablet",
            target_names=["Marcus"],
            contest_info={"type": "intimidation", "target": "Marcus"},
            anachronism_ctx=ctx,
        )

        tagged = [
            node
            for node in state.knowledge_graph.all_nodes()
            if node.source == KnowledgeSource.PERSONAL_EXPERIENCE and _FLAME in node.tags
        ]
        assert tagged, "encounter must produce a tagged memory so the familiarity counter can read it"
        assert tagged[0].salience == salience_presets.ANACHRONISM_ENCOUNTER

    @allure.title("After one encounter, a fresh per-NPC result reads a higher familiarity count")
    @pytest.mark.asyncio
    async def test_second_encounter_decays_strangeness(self):
        state = _make_state()
        marcus = _add_npc(state, _MARCUS, "Marcus")
        state.current_scene = _scene_with([(marcus, "marcus")])

        verdict = AnachronismClassification(
            strangeness_score=8,
            unfamiliar_concepts=[_FLAME],
            perceived_rewrite=_REWRITE,
        )
        classifier = _stub_classifier(verdict)
        actors = {marcus.uuid: actor_helpers.make_mock_actor(text="reply")}
        handler = DialogueHandler(state, actors, _make_memory_manager(state.knowledge_graph))

        # Pre-encounter: a fresh context sees encounter_count=0 and the
        # full base-driven strangeness. The handler hasn't run yet, so no
        # tagged memory is in the graph.
        pre_ctx = TurnAnachronismContext.create_for(classifier, state, "tablet")
        await pre_ctx.ensure_base()
        pre = pre_ctx.for_npc(marcus)

        # Run one handle_dialogue cycle. The handler ends by writing a
        # tagged memory the next turn's familiarity counter will read.
        first_ctx = TurnAnachronismContext.create_for(classifier, state, "tablet")
        await handler.handle_dialogue(
            "raise the tablet",
            target_names=["Marcus"],
            contest_info={"type": "intimidation", "target": "Marcus"},
            anachronism_ctx=first_ctx,
        )

        # Post-encounter: a NEW context (the next turn's view) reads back
        # the persisted tagged memory and discounts the verdict.
        post_ctx = TurnAnachronismContext.create_for(classifier, state, "tablet")
        await post_ctx.ensure_base()
        post = post_ctx.for_npc(marcus)

        assert post.encounter_count > pre.encounter_count
        assert post.effective_strangeness < pre.effective_strangeness
