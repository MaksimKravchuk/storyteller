"""Unit tests for the AnachronismClassifier and per-NPC modifier math."""

from __future__ import annotations

from unittest.mock import AsyncMock

import allure
import pytest

from cast import _anachronism_math as _math, anachronism as anachronism_mod
from cast.schemas import anachronism as schema_mod
from knowledge import graph as graph_mod, node as _node, query as query_mod
from llm.message import LLMResponse
from models import game_state as gs_mod, npc_card as npc_card_mod, setting as setting_mod
from tests._uuid_helpers import make_uuid

AnachronismClassifier = anachronism_mod.AnachronismClassifier
TurnAnachronismContext = anachronism_mod.TurnAnachronismContext
AnachronismClassification = schema_mod.AnachronismClassification
NPCAnachronismResult = schema_mod.NPCAnachronismResult
STRANGENESS_MAX = schema_mod.STRANGENESS_MAX
STRANGENESS_MIN = schema_mod.STRANGENESS_MIN
build_npc_result = _math.build_npc_result
compute_effective_strangeness = _math.compute_effective_strangeness
encounter_count_for_npc = _math.encounter_count_for_npc
KnowledgeGraph = graph_mod.KnowledgeGraph
KnowledgeQueryEngine = query_mod.KnowledgeQueryEngine
KnowledgeNode = _node.KnowledgeNode
KnowledgeScope = _node.KnowledgeScope
KnowledgeSource = _node.KnowledgeSource
EdgeType = _node.EdgeType
CanonSource = _node.CanonSource
GameState = gs_mod.GameState
PlayerState = gs_mod.PlayerState
NPCCard = npc_card_mod.NPCCard
Setting = setting_mod.Setting

pytestmark = [
    allure.epic("World & Setting"),
    allure.feature("Anachronism awareness"),
]

_FORUM = make_uuid("forum")
_NPC_MARCUS = make_uuid("npc-marcus")
_FLAME = "light_without_flame"
_FIRE = "light_without_fire"
_PHOTO = "image_capture"


def _make_setting() -> Setting:
    return Setting(
        name="Ancient Rome",
        time_period="1st century AD",
        region="Italy",
        summary="The Roman Empire.",
        technologies=["oil lamps", "iron tools", "horse-drawn carts"],
        social_structure="Republic with patrician/plebeian classes.",
    )


def _make_game_state(origin_era: str = "21st century earth") -> GameState:
    """Build a minimal GameState with the player wired for anachronism."""
    graph = KnowledgeGraph()
    state = GameState(
        setting=_make_setting(),
        knowledge_graph=graph,
        player=PlayerState(name="Traveller", origin_era=origin_era),
    )
    return state


def _make_npc(education: int = 5, name: str = "Marcus") -> NPCCard:
    npc = NPCCard(name=name, occupation="legionary", attributes={"education": education})
    npc.uuid = _NPC_MARCUS
    return npc


def _attach_tagged_memory(graph: KnowledgeGraph, npc_uuid, tag: str, timestamp: float) -> None:
    """Attach a personal-experience memory tagged with *tag* to *npc_uuid*."""
    node = KnowledgeNode(
        text="prior encounter",
        scope=KnowledgeScope.LOCAL,
        source=KnowledgeSource.PERSONAL_EXPERIENCE,
        canon=CanonSource.SESSION,
        timestamp=timestamp,
        tags=[tag],
    )
    graph.add_node(node)
    graph.add_edge(npc_uuid, node.uuid, EdgeType.WITNESSED)


@allure.story("Modifier math")
class TestComputeEffectiveStrangeness:
    @allure.title("Education=5 leaves the base score unchanged")
    def test_education_midpoint_is_identity(self):
        assert compute_effective_strangeness(base_score=6, education=5, encounter_count=0) == 6

    @allure.title("Low-education NPC amplifies the base strangeness")
    def test_low_education_amplifies(self):
        # education=2 → factor 1.3; round(6 * 1.3) = 8.
        assert compute_effective_strangeness(base_score=6, education=2, encounter_count=0) == 8

    @allure.title("High-education NPC discounts the base strangeness")
    def test_high_education_discounts(self):
        # education=8 → factor 0.7; round(6 * 0.7) = 4.
        assert compute_effective_strangeness(base_score=6, education=8, encounter_count=0) == 4

    @allure.title("Each prior encounter trims familiarity by 25%")
    def test_familiarity_decays_per_encounter(self):
        # base 8, education 5, two encounters → 8 * 1 * 0.5 = 4.
        assert compute_effective_strangeness(base_score=8, education=5, encounter_count=2) == 4

    @allure.title("Familiarity floor stops the discount at 20% of base")
    def test_familiarity_floor_caps_decay(self):
        # base 10, education 5, 100 encounters → 10 * 1 * 0.2 = 2 (not 0).
        assert compute_effective_strangeness(base_score=10, education=5, encounter_count=100) == 2

    @allure.title("Effective strangeness clamps to the [0, 10] axis")
    def test_clamp_into_axis(self):
        # base 10, education 0 → factor 1.5 → 15 → clamped to 10.
        assert compute_effective_strangeness(base_score=10, education=0, encounter_count=0) == STRANGENESS_MAX
        # base 0 → 0 (no negative).
        assert compute_effective_strangeness(base_score=0, education=2, encounter_count=0) == STRANGENESS_MIN


@allure.story("Familiarity counter")
class TestEncounterCountForNPC:
    @allure.title("No memories returns zero encounters")
    def test_zero_when_no_memories(self):
        graph = KnowledgeGraph()
        graph.register_actor_node(_NPC_MARCUS, label="Marcus")
        engine = KnowledgeQueryEngine(graph)
        assert encounter_count_for_npc(_NPC_MARCUS, [_FLAME], engine) == 0

    @allure.title("Same concept seen twice raises the counter to 2")
    def test_two_encounters_same_concept(self):
        graph = KnowledgeGraph()
        graph.register_actor_node(_NPC_MARCUS, label="Marcus")
        _attach_tagged_memory(graph, _NPC_MARCUS, _FLAME, timestamp=1.0)
        _attach_tagged_memory(graph, _NPC_MARCUS, _FLAME, timestamp=2.0)
        engine = KnowledgeQueryEngine(graph)
        assert encounter_count_for_npc(_NPC_MARCUS, [_FLAME], engine) == 2

    @allure.title("Fuzzy match: classifier-drifted concept tag still resolves prior encounters")
    def test_fuzzy_match_finds_prior_encounter(self):
        graph = KnowledgeGraph()
        graph.register_actor_node(_NPC_MARCUS, label="Marcus")
        # Stored as ``light_without_flame``; classifier emits ``light_without_fire`` next turn.
        _attach_tagged_memory(graph, _NPC_MARCUS, _FLAME, timestamp=1.0)
        engine = KnowledgeQueryEngine(graph)
        assert encounter_count_for_npc(_NPC_MARCUS, [_FIRE], engine) == 1

    @allure.title("min-aggregation: the least-familiar concept anchors the counter")
    def test_min_aggregation_across_concepts(self):
        graph = KnowledgeGraph()
        graph.register_actor_node(_NPC_MARCUS, label="Marcus")
        _attach_tagged_memory(graph, _NPC_MARCUS, _FLAME, timestamp=1.0)
        _attach_tagged_memory(graph, _NPC_MARCUS, _FLAME, timestamp=2.0)
        engine = KnowledgeQueryEngine(graph)
        # Marcus has seen the flame twice, but never an image_capture; the
        # brand-new concept anchors the counter so the modifier still bites.
        assert encounter_count_for_npc(_NPC_MARCUS, [_FLAME, _PHOTO], engine) == 0


@allure.story("Per-NPC result")
class TestBuildNPCResult:
    @allure.title("Period-appropriate verdict (score 0) returns score 0 regardless of NPC state")
    def test_zero_base_passes_through(self):
        graph = KnowledgeGraph()
        graph.register_actor_node(_NPC_MARCUS, label="Marcus")
        engine = KnowledgeQueryEngine(graph)
        verdict = AnachronismClassification(strangeness_score=0, unfamiliar_concepts=[], perceived_rewrite="")
        npc = _make_npc(education=2)
        result = build_npc_result(verdict, npc, engine)
        assert result.effective_strangeness == 0

    @allure.title("Two encounters with same concept reduce the second contest's strangeness")
    def test_familiarity_discount_after_repeated_exposure(self):
        graph = KnowledgeGraph()
        graph.register_actor_node(_NPC_MARCUS, label="Marcus")
        engine = KnowledgeQueryEngine(graph)
        verdict = AnachronismClassification(
            strangeness_score=8,
            unfamiliar_concepts=[_FLAME],
            perceived_rewrite="captured spark",
        )
        npc = _make_npc(education=5)

        first = build_npc_result(verdict, npc, engine)
        # Record the exposure the same way the dialogue handler would.
        _attach_tagged_memory(graph, _NPC_MARCUS, _FLAME, timestamp=1.0)
        second = build_npc_result(verdict, npc, engine)

        assert second.effective_strangeness < first.effective_strangeness

    @allure.title("Per-NPC result preserves the base verdict's concepts and rewrite")
    def test_passthrough_fields(self):
        graph = KnowledgeGraph()
        engine = KnowledgeQueryEngine(graph)
        verdict = AnachronismClassification(
            strangeness_score=5,
            unfamiliar_concepts=[_FLAME, _PHOTO],
            perceived_rewrite="bewildering tablet",
        )
        npc = _make_npc(education=5)
        result = build_npc_result(verdict, npc, engine)
        assert result.unfamiliar_concepts == [_FLAME, _PHOTO]
        assert result.perceived_rewrite == "bewildering tablet"


def _stub_classifier(verdict: AnachronismClassification) -> AnachronismClassifier:
    """Return a real classifier instance with a stub LLM client.

    The classifier's ``classify`` is patched to return the canned verdict
    so the LLM contract stays an integration concern — these unit tests
    focus on the modifier math and the cache semantics.
    """
    classifier = AnachronismClassifier(llm_client=AsyncMock())
    classifier.classify = AsyncMock(return_value=verdict)  # type: ignore[method-assign]
    return classifier


@allure.story("TurnAnachronismContext")
class TestTurnAnachronismContext:
    @allure.title("ensure_base runs the classifier exactly once across multiple awaits")
    @pytest.mark.asyncio
    async def test_ensure_base_is_idempotent(self):
        verdict = AnachronismClassification(strangeness_score=3, unfamiliar_concepts=[], perceived_rewrite="x")
        classifier = _stub_classifier(verdict)
        state = _make_game_state()
        ctx = TurnAnachronismContext.create_for(classifier, state, "raise the tablet")

        await ctx.ensure_base()
        await ctx.ensure_base()
        await ctx.ensure_base()

        classifier.classify.assert_awaited_once_with("raise the tablet", state)  # type: ignore[attr-defined]

    @allure.title("base_or_empty returns the empty sentinel before classification has run")
    def test_base_or_empty_default(self):
        classifier = _stub_classifier(AnachronismClassification(strangeness_score=0))
        state = _make_game_state()
        ctx = TurnAnachronismContext.create_for(classifier, state, "anything")
        assert ctx.base_or_empty.strangeness_score == 0
        assert ctx.base_or_empty.unfamiliar_concepts == []

    @allure.title("for_npc returns the cached verdict modulated for the NPC")
    @pytest.mark.asyncio
    async def test_for_npc_uses_cached_verdict(self):
        verdict = AnachronismClassification(
            strangeness_score=6,
            unfamiliar_concepts=[_FLAME],
            perceived_rewrite="captured spark",
        )
        classifier = _stub_classifier(verdict)
        state = _make_game_state()
        ctx = TurnAnachronismContext.create_for(classifier, state, "raise the tablet")
        await ctx.ensure_base()

        npc = _make_npc(education=5)
        state.npcs[npc.uuid] = npc
        state.knowledge_graph.register_actor_node(npc.uuid, label="Marcus")

        result = ctx.for_npc(npc)
        assert isinstance(result, NPCAnachronismResult)
        assert result.effective_strangeness == 6
        assert result.encounter_count == 0


@allure.story("Classifier feature flag")
class TestClassifierFeatureFlag:
    @allure.title("Empty origin_era short-circuits to the empty verdict (no LLM call)")
    @pytest.mark.asyncio
    async def test_empty_origin_era_skips_llm(self):
        llm = AsyncMock()
        llm.send_message = AsyncMock(
            return_value=LLMResponse(body='{"strangeness_score": 9}', model="stub", usage={}),
        )
        classifier = AnachronismClassifier(llm_client=llm)
        state = _make_game_state(origin_era="")  # disabled

        verdict = await classifier.classify("anything", state)

        assert verdict.strangeness_score == 0
        llm.send_message.assert_not_awaited()
