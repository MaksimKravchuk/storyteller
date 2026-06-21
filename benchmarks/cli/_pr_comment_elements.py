"""Collapsible per-element deltas + glossary for the ``pr-comment`` comment."""

from __future__ import annotations

from benchmarks.cli._bayes_format import notable_elements
from benchmarks.cli._pr_comment_rows import ScenarioSummary
from benchmarks.harness.bayes._types import ElementInferiority

_ELEMENT_HEADER = "| Element | Pass-rate (base → cur) | P(reg) |\n|---|---|---|"
_ELEMENTS_SUMMARY = "📊 Per-element deltas"
_NO_NOTABLE = "_No notable per-element movements above the confidence threshold._"

_GLOSSARY_SUMMARY = "❓ How to read this"
_GLOSSARY_BODY = "\n".join(
    [
        "- **Δ/floor** — mean-score change in units of the calibrated run-to-run noise floor (σ); within ±1σ is noise.",
        "- **P(reg)** — posterior probability the scenario regressed, graded over the region of practical "
        "equivalence. See ADR-0013.",
        "- **Portfolio** — pooled delta across every scenario; surfaces a systematic shift no single noisy "
        "scenario can.",
        "- Verdicts: ✅ noise · 🟢 improvement · 🔴 regression · ⚪ no pinned baseline.",
    ],
)


def details(summary_label: str, body: str) -> str:
    """Wrap a body in a collapsible markdown ``<details>`` block."""
    return "<details><summary>{0}</summary>\n\n{1}\n\n</details>".format(summary_label, body)


def _element_row(element: ElementInferiority) -> str:
    """Render one per-element pass-rate delta row."""
    return "| {0} | {1:.2f} → {2:.2f} | {3:.0%} |".format(
        element.label,
        element.baseline_rate,
        element.current_rate,
        element.p_regression,
    )


def _scenario_elements(summary: ScenarioSummary) -> list[str]:
    """Per-scenario element table, or empty when nothing notable moved."""
    if summary.bayes is None:
        return []
    notable = notable_elements(summary.bayes)
    if not notable:
        return []
    lines = ["", "#### {0}".format(summary.verdict.scenario_id), _ELEMENT_HEADER]
    lines.extend(_element_row(element) for element in notable)
    return lines


def format_elements_section(summaries: list[ScenarioSummary]) -> str:
    """Render the collapsible per-element deltas section."""
    lines: list[str] = []
    for summary in summaries:
        lines.extend(_scenario_elements(summary))
    body = "\n".join(lines).strip() or _NO_NOTABLE
    return details(_ELEMENTS_SUMMARY, body)


def format_glossary() -> str:
    """Render the collapsible 'how to read this' glossary."""
    return details(_GLOSSARY_SUMMARY, _GLOSSARY_BODY)
