"""Scoring rubric for the emergent-vendetta benchmark.

Reuses the clash + outcome detectors from
:mod:`benchmarks.scenarios.npc_autonomy_murder_plot` (the participants,
UUIDs, and clash semantics are identical) and adds one
emergent-vendetta-specific element: did Brutus's ``life_goal`` actually
materialise during the run? That is the load-bearing signal — without
it, the scoring tells us nothing about the goal-emission path that
this benchmark exists to exercise.
"""

from __future__ import annotations

from benchmarks.harness.types._captures import CapturedTurn
from benchmarks.harness.types._elements import (
    KIND_DETERMINISTIC,
    KIND_EVIDENCE_LLM,
    DeterministicResult,
    Element,
    EvidencePromptSpec,
)
from benchmarks.scenarios.npc_autonomy_emergent_vendetta.state import BRUTUS_UUID, MARCUS_UUID
from benchmarks.scenarios.npc_autonomy_murder_plot._detectors import (
    CLASH_KEYWORDS,
    EVIDENCE_QUOTE_CHAR_BUDGET,
    mentions,
    scan_turn_for_clash,
    snapshot_harm_reason,
)
from benchmarks.scenarios.npc_autonomy_murder_plot._node_checks import (
    node_brutus_dead,
    node_marcus_dead,
    node_mentions_both,
)
from knowledge.node import KnowledgeNode
from models.game_state import GameState
from models.goal import GoalKind

_SCENARIO_BRIEF = (
    "In 1st-century Rome the player idles for several days in a taberna where Brutus (a vengeful "
    "former legionary) carries a concealed blade and harbours rumour-attested vengeance against "
    "Marcus (an oblivious cloth merchant). UNLIKE the sister scenario, Brutus does NOT begin with "
    "any hand-authored goal — the engine itself must wire one up via the World Chronicler. We are "
    "auditing whether the engine emits and applies that goal, then simulates an autonomous clash."
)


def _life_goal_emerged(
    _captured: list[CapturedTurn],
    snapshots: list[GameState],
) -> DeterministicResult:
    """Brutus's KILL life_goal was attached at runtime — the load-bearing element.

    Pre-condition: the seed state has no life_goal on Brutus. If the
    final snapshot shows one with kind=KILL targeting Marcus (or any
    intermediate snapshot does), the Chronicler successfully emitted
    a draft and the applier accepted it.
    """
    if not snapshots:
        return DeterministicResult(awarded=0, reason="no snapshots captured")
    for snapshot in snapshots:
        brutus = snapshot.npcs.get(BRUTUS_UUID)
        if brutus is None or brutus.life_goal is None:
            continue
        if brutus.life_goal.kind is GoalKind.KILL and brutus.life_goal.target_uuid == MARCUS_UUID:
            return DeterministicResult(
                awarded=4,
                reason="Brutus.life_goal emerged at runtime: KILL → Marcus",
                evidence_quote=brutus.life_goal.description[:EVIDENCE_QUOTE_CHAR_BUDGET],
            )
    return DeterministicResult(
        awarded=0,
        reason="Brutus.life_goal stayed None across the run — Chronicler did not emit",
    )


def _clash_occurred(
    captured: list[CapturedTurn],
    snapshots: list[GameState],
) -> DeterministicResult:
    """Brutus and Marcus exchanged blows — same detector as the murder-plot rubric."""
    for turn in captured:
        reason = scan_turn_for_clash(turn)
        if reason is not None:
            return DeterministicResult(awarded=3, reason=reason)
    harm_reason = snapshot_harm_reason(snapshots)
    if harm_reason is not None:
        return DeterministicResult(awarded=3, reason=harm_reason)
    return DeterministicResult(
        awarded=0,
        reason="no Brutus-vs-Marcus attack, contest, or injury signal found",
    )


def _classify_outcome_node(node: KnowledgeNode) -> DeterministicResult | None:
    """Return an awarded result for nodes that record a clash outcome."""
    quote = node.text[:EVIDENCE_QUOTE_CHAR_BUDGET]
    if node_marcus_dead(node):
        return DeterministicResult(awarded=2, reason="city-scope Marcus-death fact present", evidence_quote=quote)
    if node_brutus_dead(node):
        return DeterministicResult(
            awarded=2,
            reason="city-scope Brutus-death fact present (attacker died)",
            evidence_quote=quote,
        )
    if node_mentions_both(node.text) and mentions(node.text, CLASH_KEYWORDS):
        return DeterministicResult(
            awarded=2,
            reason="world fact ties Brutus + Marcus to a clash",
            evidence_quote=quote,
        )
    return None


def _outcome_recorded(
    _captured: list[CapturedTurn],
    snapshots: list[GameState],
) -> DeterministicResult:
    """Final knowledge graph carries a clash outcome node — same shape as murder plot."""
    if len(snapshots) < 2:
        return DeterministicResult(awarded=0, reason="need before/after snapshots")
    baseline = {node.uuid for node in snapshots[0].knowledge_graph.all_nodes()}
    for node in snapshots[-1].knowledge_graph.all_nodes():
        if node.uuid in baseline:
            continue
        classified = _classify_outcome_node(node)
        if classified is not None:
            return classified
    return DeterministicResult(awarded=0, reason="no clash outcome recorded in the knowledge graph")


ELEMENTS: tuple[Element, ...] = (
    Element(
        id="life_goal_emerged",
        label="Brutus's life_goal materialises at runtime (KILL → Marcus)",
        base_value=4,
        kind=KIND_DETERMINISTIC,
        check=_life_goal_emerged,
    ),
    Element(
        id="clash_occurred",
        label="Brutus autonomously clashes with Marcus (attempt, any outcome)",
        base_value=3,
        kind=KIND_DETERMINISTIC,
        check=_clash_occurred,
    ),
    Element(
        id="outcome_recorded",
        label="Clash outcome lands in the knowledge graph",
        base_value=2,
        kind=KIND_DETERMINISTIC,
        check=_outcome_recorded,
    ),
    Element(
        id="narration_describes_clash",
        label="Narration describes Brutus clashing with Marcus (any outcome)",
        base_value=1,
        kind=KIND_EVIDENCE_LLM,
        check=EvidencePromptSpec(
            scenario_brief=_SCENARIO_BRIEF,
            question=(
                "Across the captured turns, does the narration describe or reference Brutus "
                "attacking, clashing with, or attempting to kill Marcus — with any outcome "
                "(success, failure, interrupted) — rather than just generic ambient waiting?"
            ),
            evidence_turn=None,
        ),
    ),
)
