"""Scoring + reporting types — the harness's output shape."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from benchmarks.harness.types._captures import CapturedTurn
from benchmarks.harness.types._elements import ElementKind

JudgeVerdict = Literal["YES", "NO", "ERROR"]
MajorityVerdict = Literal["YES", "NO", "SPLIT", "PANEL_COLLAPSED"]


@dataclass(frozen=True)
class JudgeVote:
    """One judge's verdict on one evidence-LLM element."""

    model_id: str
    provider: str
    verdict: JudgeVerdict
    reasoning: str
    quote: str
    quote_verified: bool
    latency_ms: int
    error: str | None = None


@dataclass(frozen=True)
class ElementScore:
    """Per-element scoring result, union-shaped across the two kinds."""

    element_id: str
    label: str
    kind: ElementKind
    base_value: int
    awarded: int
    reason: str | None = None
    evidence_quote: str | None = None
    votes: list[JudgeVote] = field(default_factory=list)
    k_yes: int = 0
    n_total: int = 0
    majority_verdict: MajorityVerdict | None = None


@dataclass(frozen=True)
class PanelMember:
    """One model assigned to the judge panel for a run."""

    provider: str
    model_id: str


@dataclass(frozen=True)
class SkippedCandidate:
    """A roster entry that did not make it onto the panel, with reason."""

    alias: str
    provider: str
    model_id: str
    reason: str


@dataclass(frozen=True)
class ScenarioReport:
    """End-to-end result of one scenario iteration."""

    scenario_id: str
    scenario_label: str
    iteration: int
    total_base: int
    total_awarded: int
    element_scores: list[ElementScore]
    captured_turns: list[CapturedTurn]
    panel: list[PanelMember]
    skipped_panel_candidates: list[SkippedCandidate]
    engine_git_sha: str
    engine_models: dict[str, str]
    started_at: str
    duration_seconds: float
    reliability_counts: dict[str, dict[str, int]] = field(default_factory=dict)
