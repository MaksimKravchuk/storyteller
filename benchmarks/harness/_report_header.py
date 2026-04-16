"""Markdown report header — title, metadata, score banner."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from benchmarks.harness.types._scores import ScenarioReport

_SMALL_PANEL_WARNING_THRESHOLD = 3
_EMPTY_PANEL_LABEL = "(empty panel)"


def _percent(awarded: int, base: int) -> int:
    """Round the ``awarded / base`` ratio to a whole percent."""
    if base == 0:
        return 0
    return round(100 * awarded / base)


def _warning_suffix(panel_size: int) -> str:
    """Return the small-panel warning badge when the panel is undersized."""
    if panel_size < _SMALL_PANEL_WARNING_THRESHOLD:
        return " ⚠ small-panel run"
    return ""


def _skip_line(skip: dict) -> str:
    """Format one skipped roster entry as a bullet."""
    model_id = skip["model_id"]
    provider = skip["provider"]
    reason = skip["reason"]
    return "- `{0}` ({1}): {2}".format(model_id, provider, reason)


def _base_header(report: ScenarioReport) -> list[str]:
    """Render the scenario identity + reproducibility lines."""
    panel_labels = ", ".join(member.model_id for member in report.panel) or _EMPTY_PANEL_LABEL
    models = report.engine_models
    return [
        "# Scenario: {0}".format(report.scenario_label),
        "",
        "- Scenario id: `{0}`".format(report.scenario_id),
        "- Iteration: {0}".format(report.iteration),
        "- Started at: {0}".format(report.started_at),
        "- Engine SHA: `{0}`".format(report.engine_git_sha or "(unset)"),
        "- Engine models: director=`{0}` agent=`{1}` narrator=`{2}`".format(
            models.get("director_model", ""),
            models.get("agent_model", ""),
            models.get("narrator_model", ""),
        ),
        "- Judge panel ({0}): {1}{2}".format(
            len(report.panel),
            panel_labels,
            _warning_suffix(len(report.panel)),
        ),
        "- Duration: {0:.1f}s".format(report.duration_seconds),
        "",
    ]


def render_header(report: ScenarioReport) -> list[str]:
    """Build the report preamble — title, metadata, score banner."""
    lines = _base_header(report)
    lines.append(
        "## Score: **{0} / {1}** ({2}%)".format(
            report.total_awarded,
            report.total_base,
            _percent(report.total_awarded, report.total_base),
        ),
    )
    lines.append("")
    if report.skipped_panel_candidates:
        lines.append("### Skipped panel candidates")
        lines.extend(_skip_line(skip) for skip in report.skipped_panel_candidates)
        lines.append("")
    return lines
