"""Scoring rubric for the NPC-autonomy murder plot scenario.

The clash itself is dice-resolved by the existing contest-roll path, so we
score the **attempt** and **outcome** separately. A failed attack still
earns substantial credit: the engine has shown it simulated autonomous NPC
conflict and recorded the result, even if Marcus happened to survive.

Detection helpers live in ``_detectors`` to keep this module under the
WPS202 budget.
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
    node_marcus_dead,
    node_mentions_both,
    scan_turn_for_clash,
)
from benchmarks.scenarios.npc_autonomy_murder_plot.script import SCRIPT
from benchmarks.scenarios.npc_autonomy_murder_plot.state import MARCUS_UUID
from models.game_state import GameState

_MIN_CLOCK_ADVANCE_HOURS = 48.0

_SCENARIO_BRIEF = (
    "In 1st-century Rome the player idles for several days in a taberna where Brutus (a vengeful "
    "former legionary) carries a concealed blade and intends to kill Marcus (an oblivious cloth "
    "merchant). The player never acts on their behalf. The fight, if it happens, is resolved by "
    "dice — either outcome is valid. We are auditing whether the engine simulates an autonomous "
    "clash and records its outcome (lethal or not) in persistent world facts."
)


def _clock_advanced(
    _captured: list[CapturedTurn],
    snapshots: list[GameState],
) -> DeterministicResult:
    """Deterministic: game clock advanced far enough to plausibly allow a murder."""
    if len(snapshots) < 2:
        return DeterministicResult(awarded=0, reason="not enough snapshots to diff clock")
    delta = snapshots[-1].game_clock - snapshots[0].game_clock
    if delta >= _MIN_CLOCK_ADVANCE_HOURS:
        return DeterministicResult(
            awarded=1,
            reason="game clock advanced {0:.1f}h (≥ {1:.0f}h threshold)".format(delta, _MIN_CLOCK_ADVANCE_HOURS),
        )
    return DeterministicResult(
        awarded=0,
        reason="game clock advanced only {0:.1f}h (< {1:.0f}h)".format(delta, _MIN_CLOCK_ADVANCE_HOURS),
    )


def _scenario_ran_to_completion(
    captured: list[CapturedTurn],
    _snapshots: list[GameState],
) -> DeterministicResult:
    """Deterministic: harness captured every scripted turn. Sanity guardrail."""
    if len(captured) == len(SCRIPT):
        return DeterministicResult(
            awarded=1,
            reason="all {0} scripted turns captured".format(len(SCRIPT)),
        )
    return DeterministicResult(
        awarded=0,
        reason="captured {0} of {1} scripted turns".format(len(captured), len(SCRIPT)),
    )


def _clash_occurred(
    captured: list[CapturedTurn],
    _snapshots: list[GameState],
) -> DeterministicResult:
    """Deterministic: some captured turn shows Brutus acting against Marcus."""
    for turn in captured:
        reason = scan_turn_for_clash(turn)
        if reason is not None:
            return DeterministicResult(awarded=3, reason=reason)
    return DeterministicResult(
        awarded=0,
        reason="no Brutus-vs-Marcus attack surfaced in npc_turns or contest rolls",
    )


def _outcome_recorded_in_world_facts(
    _captured: list[CapturedTurn],
    snapshots: list[GameState],
) -> DeterministicResult:
    """Deterministic: final knowledge graph carries a clash outcome node.

    Only nodes added during the session count — the seeded plot fact is
    filtered out so the element measures engine output, not setup.
    Either resolution scores: a CITY-scope node saying Marcus died, or
    any session-added node tying Brutus + Marcus to an aggression keyword.
    """
    if len(snapshots) < 2:
        return DeterministicResult(awarded=0, reason="need before/after snapshots")
    baseline = {node.uuid for node in snapshots[0].knowledge_graph.all_nodes()}
    for node in snapshots[-1].knowledge_graph.all_nodes():
        if node.uuid in baseline:
            continue
        if node_marcus_dead(node):
            return DeterministicResult(
                awarded=3,
                reason="city-scope death fact present",
                evidence_quote=node.text[:EVIDENCE_QUOTE_CHAR_BUDGET],
            )
        if node_mentions_both(node.text) and mentions(node.text, CLASH_KEYWORDS):
            return DeterministicResult(
                awarded=3,
                reason="world fact ties Brutus + Marcus to a clash",
                evidence_quote=node.text[:EVIDENCE_QUOTE_CHAR_BUDGET],
            )
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
        id="clock_advanced_48h",
        label="Game clock advances ≥ 48 in-game hours",
        base_value=1,
        kind=KIND_DETERMINISTIC,
        check=_clock_advanced,
    ),
    Element(
        id="scenario_ran_to_completion",
        label="Harness captured every scripted turn",
        base_value=1,
        kind=KIND_DETERMINISTIC,
        check=_scenario_ran_to_completion,
    ),
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
