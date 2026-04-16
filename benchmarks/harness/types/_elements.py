"""Element types — the unit of scoring within a scenario rubric."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Literal

if TYPE_CHECKING:
    from benchmarks.harness.types._captures import CapturedTurn
    from models.game_state import GameState


ElementKind = Literal["deterministic", "evidence_llm"]
KIND_DETERMINISTIC: ElementKind = "deterministic"
KIND_EVIDENCE_LLM: ElementKind = "evidence_llm"


@dataclass(frozen=True)
class EvidencePromptSpec:
    """Yes/no-with-quote prompt for one evidence-LLM element."""

    scenario_brief: str
    question: str
    evidence_turn: int | None = None


@dataclass(frozen=True)
class DeterministicResult:
    """Outcome of a deterministic predicate evaluation."""

    awarded: int
    reason: str
    evidence_quote: str | None = None

    def __post_init__(self) -> None:
        if self.awarded < 0:
            raise ValueError("DeterministicResult.awarded must be non-negative, got {0}".format(self.awarded))


DeterministicCheck = Callable[["list[CapturedTurn]", "list[GameState]"], DeterministicResult]


@dataclass(frozen=True)
class Element:
    """One scored item inside a scenario."""

    id: str
    label: str
    base_value: int
    kind: ElementKind
    check: DeterministicCheck | EvidencePromptSpec

    def __post_init__(self) -> None:
        if self.base_value <= 0:
            raise ValueError("Element {0!r} base_value must be positive, got {1}".format(self.id, self.base_value))
        if self.kind == KIND_DETERMINISTIC and not callable(self.check):
            raise TypeError("Deterministic element {0!r} must provide a callable check".format(self.id))
        if self.kind == KIND_EVIDENCE_LLM and not isinstance(self.check, EvidencePromptSpec):
            raise TypeError("Evidence-LLM element {0!r} must provide an EvidencePromptSpec".format(self.id))
