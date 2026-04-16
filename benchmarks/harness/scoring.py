"""Score a scenario's :class:`Element` list against captured signals.

Two element kinds, two code paths:

* **Deterministic** — the element's ``check`` is a pure callable over
  the captured turn list + GameState snapshots. Full ``base_value`` is
  awarded on a truthy result, zero otherwise.
* **Evidence-LLM** — the element's ``check`` is an
  :class:`benchmarks.harness.types.EvidencePromptSpec`. The harness
  fans the call out to every :class:`PanelMember`, collects votes, and
  awards ``round(base_value * k_yes / n_total)`` where ``k_yes`` counts
  only votes whose verdict is ``YES`` *and* whose quote was verified
  against the turn text.

Error votes (judge crashed or returned un-parseable JSON) are recorded
but do not count toward either ``k_yes`` or ``n_total``; they effectively
abstain. This keeps a flaky provider from silently penalising a run.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

from benchmarks.harness._judge_text import turn_text_for_spec
from benchmarks.harness.judge import JudgeCall, run_judge
from benchmarks.harness.types._captures import CapturedTurn
from benchmarks.harness.types._elements import DeterministicResult, Element, EvidencePromptSpec
from benchmarks.harness.types._scores import ElementScore, JudgeVote, PanelMember
from config import Config
from models.game_state import GameState

_VERDICT_YES = "YES"
_VERDICT_NO = "NO"
_VERDICT_SPLIT = "SPLIT"
_KIND_DETERMINISTIC = "deterministic"


def score_deterministic_element(
    element: Element,
    captured_turns: list[CapturedTurn],
    snapshots: list[GameState],
) -> ElementScore:
    """Evaluate a deterministic element and return its score.

    Predicates are plain callables rather than class instances, so the
    element author can inline a lambda for one-off checks. Exceptions
    are allowed to propagate — a crashing predicate is a bug in the
    scenario, not an outcome to silently record.
    """
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


def _aggregate_verdict(votes: list[JudgeVote]) -> tuple[int, int, str]:
    """Return ``(k_yes, n_total, majority)`` for a list of judge votes.

    ``n_total`` excludes error votes so an abstention does not shrink
    the denominator unfairly. ``majority`` is ``"YES"`` when YES votes
    strictly exceed NO votes, ``"NO"`` when the reverse, ``"SPLIT"`` on
    a tie (or when every judge errored).
    """
    valid = [vote for vote in votes if vote.verdict in {_VERDICT_YES, _VERDICT_NO}]
    k_yes = sum(1 for vote in valid if vote.verdict == _VERDICT_YES)
    n_total = len(valid)
    if n_total == 0:
        return 0, 0, _VERDICT_SPLIT
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
    if element.kind == _KIND_DETERMINISTIC:
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
    """Score every element in a scenario, preserving their declared order.

    Deterministic elements are evaluated synchronously in-loop;
    evidence-LLM elements are dispatched concurrently (by
    :func:`score_evidence_element`, which gathers across the panel)
    and awaited sequentially so the judge calls for one element finish
    before the next element's prompt assembly runs. This keeps the
    aggregate concurrency bounded at ``len(panel)`` judges at a time —
    well below what the current OpenAI / Anthropic SDKs rate-limit.
    """
    scores: list[ElementScore] = []
    pending = list(elements)
    while pending:
        element = pending.pop(0)
        scores.append(await _score_one(element, captured_turns, snapshots, panel=panel, cfg=cfg))
    return scores
