"""Single-agent rubric helpers — score raw agent text against an evidence rubric.

Reuses ``benchmarks/harness/scoring.score_text`` and the witness panel
plumbing without going through the scenario harness. Tests build
:class:`benchmarks.harness.types._elements.Element` instances inline
(via the :func:`ev` shorthand), call :func:`rubric_score`, and assert
via :func:`assert_rubric_pass`.

Threshold policy (codifies what the Plan agent's design recommended):

- Per-element awarded points use the existing proportional formula
  ``round(base_value * k_yes / n_total)`` from ``benchmarks.harness.scoring``.
  There is no separate per-element pass gate — the awarded value flows
  directly into the rubric total.
- A test passes when ``sum(awarded) >= round(PASS_FRACTION * sum(base_value))``,
  i.e. **70%** of the rubric's total base value. On a multi-element
  rubric this tolerates one weak element — a 3×base=2 rubric needs 4-of-6
  awarded, so one element returning 0 is still survivable.
- Collapsed panel (every element returned PANEL_COLLAPSED) → ``pytest.skip``.
  No signal, not regression.
- Panel below the signal floor (``MIN_PANEL_FOR_SIGNAL = 3`` members)
  → ``pytest.skip`` from the ``panel`` fixture. A 1-2 judge panel
  produces degenerate majority votes; better to skip than report a
  false signal.

Layer 2 elements MUST be evidence-LLM only — :class:`DeterministicCheck`
is typed against ``list[CapturedTurn]`` which raw agent text cannot
provide. Validated at the :func:`rubric_score` boundary so misuse
fails at test-collection time, not later.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

import pytest

from benchmarks.harness.scoring import score_text
from benchmarks.harness.types._elements import (
    KIND_EVIDENCE_LLM,
    Element,
    EvidencePromptSpec,
)
from benchmarks.harness.types._scores import ElementScore, PanelMember
from config import Config

# Fraction of total base value required for the test to pass.
PASS_FRACTION = 0.7
# Below this many judges, ``majority`` becomes statistical noise.
MIN_PANEL_FOR_SIGNAL = 3


def ev(
    element_id: str,
    label: str,
    brief: str,
    question: str,
    *,
    base_value: int = 2,
) -> Element:
    """Build an evidence-LLM :class:`Element` inline in a test.

    ``brief`` becomes ``EvidencePromptSpec.scenario_brief`` — context the
    judge needs to interpret the text it's about to read. ``question`` is
    the yes/no prompt the judge answers about that text. ``base_value``
    defaults to 2 (a fail-on-strong-dissent score on a 6-judge panel
    becomes 0/2; a unanimous pass becomes 2/2).
    """
    return Element(
        id=element_id,
        label=label,
        base_value=base_value,
        kind=KIND_EVIDENCE_LLM,
        check=EvidencePromptSpec(
            scenario_brief=brief,
            question=question,
            evidence_turn=None,
        ),
    )


async def rubric_score(
    text: str,
    elements: Sequence[Element],
    *,
    panel: list[PanelMember],
    cfg: Config,
) -> list[ElementScore]:
    """Score raw agent ``text`` against an evidence-LLM ``elements`` rubric.

    Validates that every element is evidence-LLM kind — a deterministic
    element passed here would have its ``check`` callable invoked with
    the wrong shape and produce a confusing TypeError deep in the call
    stack. Failing loudly at the boundary keeps the call site easy to
    debug.
    """
    for to_check in elements:
        if to_check.kind != KIND_EVIDENCE_LLM:
            raise TypeError(
                "rubric_score only accepts evidence-LLM elements; element {0!r} has kind={1!r}".format(
                    to_check.id, to_check.kind
                ),
            )
    return list(
        await asyncio.gather(
            *(score_text(text, element, panel=panel, cfg=cfg) for element in elements),
        ),
    )


def _all_panels_collapsed(scores: Sequence[ElementScore]) -> bool:
    """Return True when every element returned PANEL_COLLAPSED."""
    return all(score.majority_verdict == "PANEL_COLLAPSED" for score in scores)


def assert_rubric_pass(scores: Sequence[ElementScore]) -> None:
    """Assert the rubric reached the project's pass threshold.

    Skips (rather than fails) on a fully-collapsed panel — that's a
    no-signal condition, not a regression.
    """
    if not scores:
        raise AssertionError("rubric_score returned no elements")
    if _all_panels_collapsed(scores):
        pytest.skip("witness panel collapsed across every element — no signal")
    total_base = sum(score.base_value for score in scores)
    total_awarded = sum(score.awarded for score in scores)
    threshold = round(PASS_FRACTION * total_base)
    if total_awarded < threshold:
        breakdown = "\n".join(
            "  - {0}: {1}/{2} (k_yes={3}/{4}, majority={5})".format(
                score.element_id,
                score.awarded,
                score.base_value,
                score.k_yes,
                score.n_total,
                score.majority_verdict,
            )
            for score in scores
        )
        raise AssertionError(
            "Rubric below threshold: awarded {0}/{1}, needed {2} ({3:.0%}).\nPer-element:\n{4}".format(
                total_awarded,
                total_base,
                threshold,
                PASS_FRACTION,
                breakdown,
            ),
        )
