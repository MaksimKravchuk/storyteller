"""Scoring rubric for the grudge-formation benchmark.

All elements are deterministic snapshot reads: the clash happens away
from the player, so narration is not expected to mention it.
"""

from __future__ import annotations

from benchmarks.harness.types._captures import CapturedTurn
from benchmarks.harness.types._elements import KIND_DETERMINISTIC, DeterministicResult, Element
from benchmarks.scenarios.npc_autonomy_murder_plot._detectors import EVIDENCE_QUOTE_CHAR_BUDGET
from benchmarks.scenarios.npc_autonomy_murder_plot._node_checks import node_mentions_both
from benchmarks.scenarios.npc_autonomy_murder_plot.state import BRUTUS_UUID, MARCUS_UUID
from models.game_state import GameState
from models.goal import GoalKind
from models.npc_card import NPCCard
from models.relationship import Relationship, RelationshipKind

_GRUDGE_GOAL_KINDS = frozenset((GoalKind.KILL, GoalKind.PURSUE))
_GRUDGE_INTENSITY_CEILING = -2


def _marcus_cards(snapshots: list[GameState]) -> list[NPCCard]:
    return [snapshot.npcs[MARCUS_UUID] for snapshot in snapshots if MARCUS_UUID in snapshot.npcs]


def _is_grudge(rel: Relationship) -> bool:
    hostile = rel.kind is RelationshipKind.ENEMY and rel.intensity <= _GRUDGE_INTENSITY_CEILING
    return hostile and rel.target_uuid == str(BRUTUS_UUID)


def _grudge_relationship(_captured: list[CapturedTurn], snapshots: list[GameState]) -> DeterministicResult:
    """Marcus's directed relationship to Brutus dropped to ENEMY (intensity <= -2)."""
    grudges = [rel for marcus in _marcus_cards(snapshots) for rel in marcus.relationships if _is_grudge(rel)]
    if grudges:
        return DeterministicResult(awarded=4, reason="Marcus → Brutus: ENEMY {0}".format(grudges[0].intensity))
    return DeterministicResult(awarded=0, reason="Marcus never turned ENEMY toward Brutus")


def _grudge_goal(_captured: list[CapturedTurn], snapshots: list[GameState]) -> DeterministicResult:
    """Marcus gained a KILL/PURSUE life goal targeting Brutus."""
    for marcus in _marcus_cards(snapshots):
        goal = marcus.life_goal
        if goal is not None and goal.kind in _GRUDGE_GOAL_KINDS and goal.target_uuid == BRUTUS_UUID:
            return DeterministicResult(
                awarded=3,
                reason="Marcus.life_goal: {0} → Brutus".format(goal.kind.value),
                evidence_quote=goal.description[:EVIDENCE_QUOTE_CHAR_BUDGET],
            )
    return DeterministicResult(awarded=0, reason="Marcus never gained a grudge goal against Brutus")


def _clash_remembered(_captured: list[CapturedTurn], snapshots: list[GameState]) -> DeterministicResult:
    """The off-scene clash left a memory node naming both men."""
    if len(snapshots) < 2:
        return DeterministicResult(awarded=0, reason="need before/after snapshots")
    baseline = {node.uuid for node in snapshots[0].knowledge_graph.all_nodes()}
    for node in snapshots[-1].knowledge_graph.all_nodes():
        is_new = node.uuid not in baseline
        if is_new and node_mentions_both(node.text):
            return DeterministicResult(
                awarded=2,
                reason="memory node records the Brutus/Marcus clash",
                evidence_quote=node.text[:EVIDENCE_QUOTE_CHAR_BUDGET],
            )
    return DeterministicResult(awarded=0, reason="no memory node names both Brutus and Marcus")


ELEMENTS: tuple[Element, ...] = (
    Element(
        id="grudge_relationship",
        label="Wounded Marcus turns ENEMY toward Brutus",
        base_value=4,
        kind=KIND_DETERMINISTIC,
        check=_grudge_relationship,
    ),
    Element(
        id="grudge_goal",
        label="Marcus gains a KILL/PURSUE goal against Brutus",
        base_value=3,
        kind=KIND_DETERMINISTIC,
        check=_grudge_goal,
    ),
    Element(
        id="clash_remembered",
        label="Off-scene clash lands in the knowledge graph",
        base_value=2,
        kind=KIND_DETERMINISTIC,
        check=_clash_remembered,
    ),
)
