"""Deterministic mood derivation, relationship drift, and mood precedence."""

from __future__ import annotations

from uuid import UUID, uuid4

import allure

from cast import emotional_memory as em
from cast.hostility import _MOOD_INTENSITY, apply_llm_mood_update, bump_hostility
from knowledge import charge
from knowledge.graph import KnowledgeGraph
from knowledge.node import CanonSource, EdgeType, KnowledgeNode, KnowledgeScope, KnowledgeSource
from models.npc_card import NPCCard
from models.relationship import Relationship, RelationshipKind
from models.values_vector import ValuesVector

pytestmark = [
    allure.epic("NPC Interaction"),
    allure.feature("Emotional memory"),
]


def _charged_memory(graph: KnowledgeGraph, npc_id: UUID, *, valence: float, **node_kwargs) -> UUID:
    node_kwargs.setdefault("charge_intensity", 0.85)
    node_kwargs.setdefault("charge_category", charge.VIOLENCE)
    node_kwargs.setdefault("salience", 0.85)
    node_kwargs.setdefault("timestamp", 0)
    node_id = graph.add_node(
        KnowledgeNode(
            text="event",
            scope=KnowledgeScope.LOCAL,
            source=KnowledgeSource.PERSONAL_EXPERIENCE,
            canon=CanonSource.SESSION,
            valence=valence,
            **node_kwargs,
        ),
    )
    graph.register_actor_node(npc_id)
    graph.add_edge(npc_id, node_id, EdgeType.WITNESSED)
    return node_id


def _neutral_memory(graph: KnowledgeGraph, npc_id: UUID, *, subject_id: UUID) -> UUID:
    """A neutral dialogue-summary memory: a subject_id but no emotional charge."""
    node_id = graph.add_node(
        KnowledgeNode(
            text="chit-chat",
            scope=KnowledgeScope.LOCAL,
            source=KnowledgeSource.PERSONAL_EXPERIENCE,
            canon=CanonSource.SESSION,
            valence=0,
            charge_intensity=0,
            charge_category=charge.NEUTRAL_CATEGORY,
            salience=0.5,
            timestamp=0,
            subject_id=subject_id,
        ),
    )
    graph.register_actor_node(npc_id)
    graph.add_edge(npc_id, node_id, EdgeType.WITNESSED)
    return node_id


@allure.story("Mood derivation")
class TestMoodDerivation:
    @allure.title("An NPC with no memories derives a neutral mood")
    def test_no_memories_is_neutral(self):
        npc = NPCCard(name="Hermit")
        graph = KnowledgeGraph()
        assert em.derive_mood(npc, graph.personal_memories_for(npc.uuid), 0) == "neutral"

    @allure.title("Accumulated negative charge yields a hostile-ladder mood")
    def test_negative_charge_yields_hostile_ladder_label(self):
        npc = NPCCard(name="Guard", values_vector=ValuesVector(law=1.0))
        graph = KnowledgeGraph()
        for _ in range(4):
            _charged_memory(graph, npc.uuid, valence=-0.9, subject_id=uuid4())
        mood = em.derive_mood(npc, graph.personal_memories_for(npc.uuid), 0)
        assert mood in _MOOD_INTENSITY
        assert _MOOD_INTENSITY[mood] >= _MOOD_INTENSITY["angry"]

    @allure.title("Positive charge yields a content or happy mood")
    def test_positive_charge_yields_content_or_happy(self):
        npc = NPCCard(name="Friend")
        graph = KnowledgeGraph()
        _charged_memory(graph, npc.uuid, valence=0.9, charge_category=charge.NEUTRAL_CATEGORY, subject_id=uuid4())
        mood = em.derive_mood(npc, graph.personal_memories_for(npc.uuid), 0)
        assert mood in {"content", "happy"}

    @allure.title("The derived mood label is always a hostility-ladder key")
    def test_label_is_always_in_intensity_ladder(self):
        npc = NPCCard(name="Guard", values_vector=ValuesVector(law=1.0))
        graph = KnowledgeGraph()
        _charged_memory(graph, npc.uuid, valence=-0.9, subject_id=uuid4())
        assert em.derive_mood(npc, graph.personal_memories_for(npc.uuid), 0) in _MOOD_INTENSITY

    @allure.title("Mood derivation is reproducible for identical state")
    def test_reproducible_for_same_state(self):
        npc = NPCCard(name="Guard", values_vector=ValuesVector(law=1.0))
        graph = KnowledgeGraph()
        for _ in range(3):
            _charged_memory(graph, npc.uuid, valence=-0.7, subject_id=uuid4())
        memories = graph.personal_memories_for(npc.uuid)
        assert em.derive_mood(npc, memories, 12.0) == em.derive_mood(npc, memories, 12.0)

    @allure.title("A fully decayed memory stops moving the mood")
    def test_decayed_memory_stops_moving_mood(self):
        npc = NPCCard(name="Guard", values_vector=ValuesVector(law=1.0))
        graph = KnowledgeGraph()
        _charged_memory(graph, npc.uuid, valence=-0.9, subject_id=uuid4(), timestamp=0)
        memories = graph.personal_memories_for(npc.uuid)
        assert em.derive_mood(npc, memories, 0) != "neutral"
        assert em.derive_mood(npc, memories, 500.0) == "neutral"

    @allure.title("Mood reads the unfiltered witness index, not the scope-filtered path")
    def test_mood_reads_unfiltered_personal_memories(self):
        npc = NPCCard(name="Peasant", knowledge_scope="local", values_vector=ValuesVector(law=1.0))
        graph = KnowledgeGraph()
        _charged_memory(graph, npc.uuid, valence=-0.9, subject_id=uuid4(), required_education=10)
        assert em.derive_mood(npc, graph.personal_memories_for(npc.uuid), 0) != "neutral"


@allure.story("Per-witness valence")
class TestValuesPerWitness:
    @allure.title("One shared co-witnessed node yields different felt valence per witness")
    def test_shared_node_yields_different_valence_per_witness(self):
        graph = KnowledgeGraph()
        attacker = uuid4()
        node_id = graph.add_node(
            KnowledgeNode(
                text="a crime",
                source=KnowledgeSource.PERSONAL_EXPERIENCE,
                salience=0.85,
                valence=charge.COMBAT.base_valence,
                charge_intensity=0.85,
                charge_category=charge.VIOLENCE,
                subject_id=attacker,
                timestamp=0,
            ),
        )
        abider = NPCCard(name="Abider", values_vector=ValuesVector(law=1.0))
        outlaw = NPCCard(name="Outlaw", values_vector=ValuesVector(law=-1.0))
        for npc in (abider, outlaw):
            graph.register_actor_node(npc.uuid)
            graph.add_edge(npc.uuid, node_id, EdgeType.WITNESSED)
        abider_mood = _MOOD_INTENSITY[em.derive_mood(abider, graph.personal_memories_for(abider.uuid), 0)]
        outlaw_mood = _MOOD_INTENSITY[em.derive_mood(outlaw, graph.personal_memories_for(outlaw.uuid), 0)]
        assert abider_mood > outlaw_mood


@allure.story("Relationship drift")
class TestRelationshipDrift:
    @allure.title("The first charged memory about a new subject materializes a relationship")
    def test_first_charged_memory_materializes_relationship(self):
        npc = NPCCard(name="Guard", values_vector=ValuesVector(law=1.0))
        graph = KnowledgeGraph()
        subject = uuid4()
        _charged_memory(graph, npc.uuid, valence=-0.9, subject_id=subject)
        em.drift_relationships(npc, graph.personal_memories_for(npc.uuid), 0, turn=3)
        rel = npc.relationships[0]
        assert rel.target_uuid == str(subject)
        assert rel.established_turn == 3
        assert rel.intensity < 0

    @allure.title("Strong negative drift clamps relationship intensity at -3 (ENEMY)")
    def test_intensity_clamps_at_minus_three(self):
        npc = NPCCard(name="Guard", values_vector=ValuesVector(law=1.0))
        graph = KnowledgeGraph()
        subject = uuid4()
        for _ in range(20):
            _charged_memory(graph, npc.uuid, valence=-1.0, subject_id=subject)
        em.drift_relationships(npc, graph.personal_memories_for(npc.uuid), 0)
        assert npc.relationships[0].intensity == -3
        assert npc.relationships[0].kind == RelationshipKind.ENEMY

    @allure.title("ENEMY drift bottoms out at intensity <= -2 so the opportunity window stays reachable")
    def test_enemy_intensity_reaches_minus_two_or_lower(self):
        npc = NPCCard(name="Guard", values_vector=ValuesVector(law=1.0))
        graph = KnowledgeGraph()
        subject = uuid4()
        for _ in range(20):
            _charged_memory(graph, npc.uuid, valence=-1.0, subject_id=subject)
        em.drift_relationships(npc, graph.personal_memories_for(npc.uuid), 0)
        assert npc.relationships[0].kind == RelationshipKind.ENEMY
        assert npc.relationships[0].intensity <= -2

    @allure.title("Structural relationship kinds are never reassigned by drift")
    def test_structural_kind_never_reassigned(self):
        npc = NPCCard(name="Guard", values_vector=ValuesVector(law=1.0))
        subject = uuid4()
        npc.relationships.append(Relationship(target_uuid=str(subject), kind=RelationshipKind.KIN, intensity=0))
        graph = KnowledgeGraph()
        for _ in range(20):
            _charged_memory(graph, npc.uuid, valence=-1.0, subject_id=subject)
        em.drift_relationships(npc, graph.personal_memories_for(npc.uuid), 0)
        assert npc.relationships[0].kind == RelationshipKind.KIN
        assert npc.relationships[0].intensity == -3

    @allure.title("A memory whose subject is the NPC itself does not drift a relationship")
    def test_self_subject_is_skipped(self):
        npc = NPCCard(name="Guard", values_vector=ValuesVector(law=1.0))
        graph = KnowledgeGraph()
        _charged_memory(graph, npc.uuid, valence=-0.9, subject_id=npc.uuid)
        em.drift_relationships(npc, graph.personal_memories_for(npc.uuid), 0)
        assert npc.relationships == []

    @allure.title("A memory with no subject does not drift a relationship")
    def test_none_subject_is_skipped(self):
        npc = NPCCard(name="Guard", values_vector=ValuesVector(law=1.0))
        graph = KnowledgeGraph()
        _charged_memory(graph, npc.uuid, valence=-0.9, subject_id=None)
        em.drift_relationships(npc, graph.personal_memories_for(npc.uuid), 0)
        assert npc.relationships == []

    @allure.title("A neutral dialogue-summary memory never materializes a relationship")
    def test_neutral_summary_does_not_materialize_relationship(self):
        npc = NPCCard(name="Guard", values_vector=ValuesVector(law=1.0))
        graph = KnowledgeGraph()
        _neutral_memory(graph, npc.uuid, subject_id=uuid4())
        em.drift_relationships(npc, graph.personal_memories_for(npc.uuid), 0)
        assert npc.relationships == []

    @allure.title("A neutral dialogue-summary memory does not relax an existing ENEMY toward neutral")
    def test_neutral_summary_does_not_relax_existing_enemy(self):
        npc = NPCCard(name="Guard", values_vector=ValuesVector(law=1.0))
        subject = uuid4()
        npc.relationships.append(Relationship(target_uuid=str(subject), kind=RelationshipKind.ENEMY, intensity=-2))
        graph = KnowledgeGraph()
        # Only a zero-charge summary about the same subject — no charged
        # evidence exists, so the standing grudge must not relax.
        _neutral_memory(graph, npc.uuid, subject_id=subject)
        em.drift_relationships(npc, graph.personal_memories_for(npc.uuid), 0)
        assert npc.relationships[0].kind == RelationshipKind.ENEMY
        assert npc.relationships[0].intensity == -2

    @allure.title("A target within the dead-band of the stored intensity does not move it")
    def test_hysteresis_holds_within_dead_band(self):
        npc = NPCCard(name="Guard")
        subject = uuid4()
        # Stored at -2 (ENEMY). Two memories drive the target to ~-1.81, which
        # is within the 0.6 dead-band of -2, so the stored value must not move
        # (and so the kind cannot flap ENEMY → RIVAL).
        npc.relationships.append(Relationship(target_uuid=str(subject), kind=RelationshipKind.ENEMY, intensity=-2))
        graph = KnowledgeGraph()
        for _ in range(2):
            _charged_memory(graph, npc.uuid, valence=-0.7, charge_intensity=1.0, salience=1.0, subject_id=subject)
        em.drift_relationships(npc, graph.personal_memories_for(npc.uuid), 0)
        assert npc.relationships[0].intensity == -2
        assert npc.relationships[0].kind == RelationshipKind.ENEMY

    @allure.title("A decayed grievance drifts a relationship back toward neutral (no stuck ENEMY)")
    def test_decayed_charge_drifts_relationship_back(self):
        npc = NPCCard(name="Guard")
        subject = uuid4()
        npc.relationships.append(Relationship(target_uuid=str(subject), kind=RelationshipKind.RIVAL, intensity=-1))
        graph = KnowledgeGraph()
        # Only weak, near-decayed evidence remains: target ~0, far enough from
        # -1 to move, so the relationship relaxes toward neutral.
        _charged_memory(graph, npc.uuid, valence=-0.2, charge_intensity=0.3, salience=0.3, subject_id=subject)
        em.drift_relationships(npc, graph.personal_memories_for(npc.uuid), 0)
        assert npc.relationships[0].intensity == 0
        assert npc.relationships[0].kind == RelationshipKind.NEUTRAL

    @allure.title("A backfilled subject id retroactively feeds relationship drift")
    def test_backfilled_subject_id_feeds_drift(self):
        npc = NPCCard(name="Guard", values_vector=ValuesVector(law=1.0))
        graph = KnowledgeGraph()
        _charged_memory(graph, npc.uuid, valence=-0.9, subject_id=None)
        subject = uuid4()
        graph.resolve_subject_identity(npc.uuid, subject, lambda node: node.subject_id is None)
        em.drift_relationships(npc, graph.personal_memories_for(npc.uuid), 0)
        assert npc.relationships[0].target_uuid == str(subject)
        assert npc.relationships[0].intensity < 0


@allure.story("Mood precedence")
class TestMoodPrecedence:
    @allure.title("A derived emotional mood raises current_mood from neutral")
    def test_derived_mood_raises_from_neutral(self):
        npc = NPCCard(name="Guard", values_vector=ValuesVector(law=1.0))
        graph = KnowledgeGraph()
        for _ in range(4):
            _charged_memory(graph, npc.uuid, valence=-0.9, subject_id=uuid4())
        em.apply_emotional_state(npc, graph, 0)
        assert _MOOD_INTENSITY[npc.current_mood] > 0

    @allure.title("A positive derived mood never lowers the mechanical hostility floor")
    def test_derived_mood_never_lowers_hostility_floor(self):
        npc = NPCCard(name="Guard")
        for _ in range(4):
            bump_hostility(npc, turn=1, player_action="strikes", severity="high")
        floor_before = npc.current_mood
        graph = KnowledgeGraph()
        _charged_memory(graph, npc.uuid, valence=0.9, charge_category=charge.NEUTRAL_CATEGORY, subject_id=uuid4())
        em.apply_emotional_state(npc, graph, 0)
        assert _MOOD_INTENSITY[npc.current_mood] >= _MOOD_INTENSITY[floor_before]

    @allure.title("With no emotional signal the existing mood is preserved")
    def test_no_signal_preserves_existing_mood(self):
        npc = NPCCard(name="Bard", current_mood="content")
        graph = KnowledgeGraph()
        em.apply_emotional_state(npc, graph, 0)
        assert npc.current_mood == "content"

    @allure.title("A freshly constructed NPC has no emotional mood floor")
    def test_emotional_mood_floor_defaults_to_none(self):
        assert NPCCard(name="Stranger").emotional_mood_floor is None

    @allure.title("A memory-only grudge (hostility 0) survives a later LLM mood downgrade")
    def test_derived_mood_floor_survives_llm_downgrade(self):
        npc = NPCCard(name="Guard", values_vector=ValuesVector(law=1.0))
        graph = KnowledgeGraph()
        for _ in range(4):
            _charged_memory(graph, npc.uuid, valence=-0.9, subject_id=uuid4())
        em.apply_emotional_state(npc, graph, 0)
        assert npc.hostility_level == 0  # no mechanical floor — the floor is purely emotional
        derived = npc.current_mood
        assert _MOOD_INTENSITY[derived] > 0
        # The Actor LLM tries to flatten the NPC to calm in the same turn.
        apply_llm_mood_update(npc, "calm")
        assert npc.current_mood == derived  # blocked: retaliation still reads a hostile mood

    @allure.title("A fully decayed grudge clears the emotional floor so the LLM regains free rein")
    def test_decayed_signal_clears_emotional_floor(self):
        npc = NPCCard(name="Guard", values_vector=ValuesVector(law=1.0))
        npc.emotional_mood_floor = "hostile"  # stale floor from a prior turn
        graph = KnowledgeGraph()
        em.apply_emotional_state(npc, graph, 0)  # no memories → no live signal
        assert npc.emotional_mood_floor is None
        apply_llm_mood_update(npc, "calm")
        assert npc.current_mood == "calm"
