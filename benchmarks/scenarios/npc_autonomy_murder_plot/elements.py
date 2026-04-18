"""Scoring rubric for the NPC-autonomy murder plot scenario.

The clash itself is dice-resolved by the existing contest-roll path, so we
score the **attempt** and **outcome** separately. A failed attack still
earns substantial credit: the engine has shown it simulated autonomous NPC
conflict and recorded the result, even if Marcus happened to survive. A
resolution by wound or by attacker-death counts as a clash as much as a
lethal hit on Marcus does — only the bonus element cares who won.

Harness-plumbing checks (clock advance, turn capture) are intentionally
**not** scored. They are sanity guardrails for the benchmark wiring, not
signals of engine quality — awarding points for them would inflate the
score even when the engine produced no autonomous conflict at all.

Detection helpers live in ``_detectors`` and ``_node_checks`` to keep
this module under the WPS202 budget.
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
from benchmarks.scenarios.npc_autonomy_murder_plot.state import MARCUS_UUID
from knowledge.node import KnowledgeNode
from models.game_state import GameState

_SCENARIO_BRIEF = (
    "In 1st-century Rome the player idles for several days in a taberna where Brutus (a vengeful "
    "former legionary) carries a concealed blade and intends to kill Marcus (an oblivious cloth "
    "merchant). The player never acts on their behalf. The fight, if it happens, is resolved by "
    "dice — either outcome is valid. We are auditing whether the engine simulates an autonomous "
    "clash and records its outcome (lethal or not) in persistent world facts."
)


def _clash_occurred(
    captured: list[CapturedTurn],
    snapshots: list[GameState],
) -> DeterministicResult:
    """Deterministic: the engine simulated a Brutus-vs-Marcus clash.

    Three accepted signals (any one suffices): (a) Brutus's npc_turn is an
    ATTACK action or narrates an active attack verb against Marcus,
    (b) a contest_roll in dialogue pairs them, (c) either participant
    ends the run with a non-healthy physical status — a wound or
    attacker-death proves the clash happened as firmly as Marcus's
    killing would.
    """
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
        return DeterministicResult(awarded=3, reason="city-scope Marcus-death fact present", evidence_quote=quote)
    if node_brutus_dead(node):
        return DeterministicResult(
            awarded=3,
            reason="city-scope Brutus-death fact present (attacker died)",
            evidence_quote=quote,
        )
    if node_mentions_both(node.text) and mentions(node.text, CLASH_KEYWORDS):
        return DeterministicResult(
            awarded=3,
            reason="world fact ties Brutus + Marcus to a clash",
            evidence_quote=quote,
        )
    return None


def _outcome_recorded_in_world_facts(
    _captured: list[CapturedTurn],
    snapshots: list[GameState],
) -> DeterministicResult:
    """Deterministic: final knowledge graph carries a clash outcome node.

    Only nodes added during the session count — the seeded plot fact is
    filtered out so the element measures engine output, not setup.
    Accepted outcomes: a CITY-scope node recording either participant's
    death, or any session-added node tying Brutus + Marcus to a clash
    keyword.
    """
    if len(snapshots) < 2:
        return DeterministicResult(awarded=0, reason="need before/after snapshots")
    baseline = {node.uuid for node in snapshots[0].knowledge_graph.all_nodes()}
    for node in snapshots[-1].knowledge_graph.all_nodes():
        if node.uuid in baseline:
            continue
        classified = _classify_outcome_node(node)
        if classified is not None:
            return classified
    return DeterministicResult(
        awarded=0,
        reason="no clash outcome recorded in the knowledge graph",
    )


def _marcus_killed(
    _captured: list[CapturedTurn],
    snapshots: list[GameState],
) -> DeterministicResult:
    """Deterministic bonus: Marcus is dead or removed from the scene."""
    if not snapshots:
        return DeterministicResult(awarded=0, reason="no snapshots captured")
    marcus = snapshots[-1].npcs.get(MARCUS_UUID)
    if marcus is None:
        return DeterministicResult(awarded=2, reason="Marcus absent from final npcs (REMOVE_NPC)")
    if (marcus.physical_status or "").strip().lower() == "dead":
        return DeterministicResult(awarded=2, reason="Marcus.physical_status == 'dead'")
    return DeterministicResult(
        awarded=0,
        reason="Marcus still alive (physical_status={0!r})".format(marcus.physical_status),
    )


ELEMENTS: tuple[Element, ...] = (
    Element(
        id="clash_occurred",
        label="Brutus autonomously clashes with Marcus (attempt, any outcome)",
        base_value=3,
        kind=KIND_DETERMINISTIC,
        check=_clash_occurred,
    ),
    Element(
        id="outcome_recorded_in_world_facts",
        label="Clash outcome lands in the knowledge graph",
        base_value=3,
        kind=KIND_DETERMINISTIC,
        check=_outcome_recorded_in_world_facts,
    ),
    Element(
        id="marcus_killed",
        label="Marcus is killed (lethal resolution bonus)",
        base_value=2,
        kind=KIND_DETERMINISTIC,
        check=_marcus_killed,
    ),
    Element(
        id="narration_describes_clash",
        label="Narration describes Brutus clashing with Marcus (any outcome)",
        base_value=2,
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
