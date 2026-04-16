"""Score a scenario's Element list against captured turns + GameState snapshots."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

from benchmarks.harness._judge_text import turn_text_for_spec
from benchmarks.harness.judge import JudgeCall, run_judge
from benchmarks.harness.types._captures import CapturedTurn
from benchmarks.harness.types._elements import (
    KIND_DETERMINISTIC,
    DeterministicResult,
    Element,
    EvidencePromptSpec,
)
from benchmarks.harness.types._scores import (
    ElementScore,
    JudgeVote,
    MajorityVerdict,
    PanelMember,
)
from config import Config
from models.game_state import GameState

_VERDICT_YES: MajorityVerdict = "YES"
_VERDICT_NO: MajorityVerdict = "NO"
_VERDICT_SPLIT: MajorityVerdict = "SPLIT"
_VERDICT_PANEL_COLLAPSED: MajorityVerdict = "PANEL_COLLAPSED"


def score_deterministic_element(
    element: Element,
    captured_turns: list[CapturedTurn],
    snapshots: list[GameState],
) -> ElementScore:
    """Evaluate a deterministic element and return its score."""
    if not callable(element.check):
        raise TypeError(
            "Deterministic element {0!r} must provide a callable check".format(element.id),
        )
    verdict: DeterministicResult = element.check(captured_turns, snapshots)
    awarded = min(max(verdict.awarded, 0), element.base_value)
    return ElementScore(
        element_id=element.id,
        label=element.label,
        kind=element.kind,
        base_value=element.base_value,
        awarded=awarded,
        reason=verdict.reason,
        evidence_quote=verdict.evidence_quote,
    )


def _aggregate_verdict(votes: list[JudgeVote]) -> tuple[int, int, MajorityVerdict]:
    """Return ``(k_yes, n_total, majority)`` for a list of judge votes."""
    valid = [vote for vote in votes if vote.verdict in {_VERDICT_YES, _VERDICT_NO}]
    k_yes = sum(1 for vote in valid if vote.verdict == _VERDICT_YES)
    n_total = len(valid)
    if n_total == 0:
        return 0, 0, _VERDICT_PANEL_COLLAPSED
    if k_yes * 2 > n_total:
        return k_yes, n_total, _VERDICT_YES
    if k_yes * 2 < n_total:
        return k_yes, n_total, _VERDICT_NO
    return k_yes, n_total, _VERDICT_SPLIT


def _evidence_awarded(base_value: int, k_yes: int, n_total: int) -> int:
    """Proportional credit ``round(base_value * k_yes / n_total)`` with guard."""
    if n_total == 0:
        return 0
    return round(base_value * k_yes / n_total)


async def score_evidence_element(
    element: Element,
    captured_turns: list[CapturedTurn],
    *,
    panel: list[PanelMember],
    cfg: Config,
) -> ElementScore:
    """Evaluate an evidence-LLM element by polling every panel member."""
    if not isinstance(element.check, EvidencePromptSpec):
        raise TypeError(
            "Evidence-LLM element {0!r} must provide an EvidencePromptSpec".format(element.id),
        )
    call = JudgeCall(spec=element.check, turn_text=turn_text_for_spec(element.check, captured_turns))
    vote_list = list(
        await asyncio.gather(*(run_judge(member, call, cfg=cfg) for member in panel)),
    )
    k_yes, n_total, majority = _aggregate_verdict(vote_list)
    return ElementScore(
        element_id=element.id,
        label=element.label,
        kind=element.kind,
        base_value=element.base_value,
        awarded=_evidence_awarded(element.base_value, k_yes, n_total),
        votes=vote_list,
        k_yes=k_yes,
        n_total=n_total,
        majority_verdict=majority,
    )


async def _score_one(
    element: Element,
    captured_turns: list[CapturedTurn],
    snapshots: list[GameState],
    *,
    panel: list[PanelMember],
    cfg: Config,
) -> ElementScore:
    """Dispatch one element to its deterministic or evidence scorer."""
    if element.kind == KIND_DETERMINISTIC:
        return score_deterministic_element(element, captured_turns, snapshots)
    return await score_evidence_element(element, captured_turns, panel=panel, cfg=cfg)


async def score_scenario(
    elements: Sequence[Element],
    captured_turns: list[CapturedTurn],
    snapshots: list[GameState],
    *,
    panel: list[PanelMember],
    cfg: Config,
) -> list[ElementScore]:
    """Score every element in a scenario, preserving their declared order."""
    scores: list[ElementScore] = []
    pending = list(elements)
    while pending:
        element = pending.pop(0)
        scores.append(await _score_one(element, captured_turns, snapshots, panel=panel, cfg=cfg))
    return scores
