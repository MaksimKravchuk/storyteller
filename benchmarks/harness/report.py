"""Render a :class:`ScenarioReport` as markdown for humans."""

from __future__ import annotations

from typing import TYPE_CHECKING

from benchmarks.harness._report_appendix import render_appendix
from benchmarks.harness._report_elements import render_element_table
from benchmarks.harness._report_header import render_header
from benchmarks.harness._report_turns import render_turn_log

if TYPE_CHECKING:
    from benchmarks.harness.types._scores import ScenarioReport


def render_markdown(report: ScenarioReport) -> str:
    """Return the full markdown report for a single scenario iteration."""
    lines = render_header(report)
    lines.extend(render_element_table(report.element_scores))
    lines.append("")
    lines.extend(render_appendix(report.element_scores))
    lines.append("")
    lines.extend(render_turn_log(report))
    return "\n".join(lines)
