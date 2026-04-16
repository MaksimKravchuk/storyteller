"""Element types — the unit of scoring within a scenario rubric."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Literal

if TYPE_CHECKING:
    from benchmarks.harness.types._captures import CapturedTurn
    from models.game_state import GameState


ElementKind = Literal["deterministic", "evidence_llm"]


@dataclass(frozen=True)
class EvidencePromptSpec:
    """Declarative spec for an evidence-LLM element.

    ``scenario_brief`` is the short framing passed to every judge (so the
    judge knows what the session is about without receiving the whole
    transcript). ``question`` is the single yes/no-with-quote query the
    judge must answer. ``evidence_turn`` pins which captured turn's
    narration + dialogue the quote has to come from; when ``None``, the
    harness concatenates all recorded turns.
    """

    scenario_brief: str
    question: str
    evidence_turn: int | None = None


@dataclass(frozen=True)
class DeterministicResult:
    """Outcome of a deterministic predicate evaluation."""

    awarded: int
    reason: str
    evidence_quote: str | None = None


# Signature of a deterministic element predicate. Receives the captured
# turn record list and the ordered GameState snapshots (one before
# turn 0 plus one after each turn) and returns a :class:`DeterministicResult`.
DeterministicCheck = Callable[["list[CapturedTurn]", "list[GameState]"], DeterministicResult]


@dataclass(frozen=True)
class Element:
    """One scored item inside a scenario.

    ``base_value`` is the maximum points the element can contribute to
    the scenario score. ``kind`` selects the scoring backend:

    * ``deterministic`` — ``check`` must be a :data:`DeterministicCheck`
      callable; it is evaluated locally without any LLM call.
    * ``evidence_llm`` — ``check`` must be an :class:`EvidencePromptSpec`;
      the harness fans it out to every judge in the witness panel and
      aggregates proportional credit from the valid-YES count.
    """

    id: str
    label: str
    base_value: int
    kind: ElementKind
    check: DeterministicCheck | EvidencePromptSpec
