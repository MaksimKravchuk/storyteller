"""Scoring + reporting types — the harness's output shape."""

from __future__ import annotations

from dataclasses import dataclass, field

from benchmarks.harness.types._captures import CapturedTurn
from benchmarks.harness.types._elements import ElementKind


@dataclass
class JudgeVote:
    """One judge's verdict on one evidence-LLM element."""

    model_id: str
    provider: str
    verdict: str  # "YES" | "NO" | "ERROR"
    reasoning: str
    quote: str
    quote_verified: bool
    latency_ms: int
    error: str | None = None


@dataclass
class ElementScore:
    """Per-element scoring result, union-shaped across the two kinds."""

    element_id: str
    label: str
    kind: ElementKind
    base_value: int
    awarded: int
    # Deterministic fields
    reason: str | None = None
    evidence_quote: str | None = None
    # Evidence-LLM fields
    votes: list[JudgeVote] = field(default_factory=list)
    k_yes: int = 0
    n_total: int = 0
    majority_verdict: str | None = None


@dataclass
class PanelMember:
    """One model assigned to the judge panel for a run."""

    provider: str
    model_id: str


@dataclass
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
    skipped_panel_candidates: list[dict]
    engine_git_sha: str
    engine_models: dict[str, str]
    started_at: str
    duration_seconds: float
