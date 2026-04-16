"""Implementation of the ``benchmarks compare`` subcommand."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from benchmarks.cli._writer import Writer, default_writer

_LABEL_COL_WIDTH = 40


def _load_report_payload(path: str) -> dict:
    """Read a JSON report from disk, raising a friendly error on miss."""
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError("Report not found: {0}".format(path))
    return json.loads(file_path.read_text(encoding="utf-8"))


def _format_report_header(tag: str, report: dict) -> str:
    """Format the baseline/current header line."""
    return "{0}: {1} iter={2}  total={3}/{4}".format(
        tag,
        report["scenario_id"],
        report["iteration"],
        report["total_awarded"],
        report["total_base"],
    )


def _format_panel_note(current_score: dict, baseline_score: dict) -> str:
    """Render the agreement cell for one element."""
    if current_score["kind"] == "evidence_llm":
        return "{0}→{1} YES".format(baseline_score.get("k_yes", 0), current_score["k_yes"])
    return "det."


def _format_element_row(current_score: dict, baseline_score: dict) -> str:
    """Format one element delta row for the compare table."""
    delta = current_score["awarded"] - baseline_score.get("awarded", 0)
    return "{label:<40} {base:>8} {delta:>+8} {panel:>8}".format(
        label=current_score["label"][:_LABEL_COL_WIDTH],
        base=current_score["base_value"],
        delta=delta,
        panel=_format_panel_note(current_score, baseline_score),
    )


def _print_compare_table(baseline: dict, current: dict, writer: Writer) -> None:
    """Print the per-element delta table."""
    writer("\n{0:<40} {1:>8} {2:>8} {3:>8}".format("element", "base", "Δ", "panel"))
    baseline_index = {score["element_id"]: score for score in baseline["element_scores"]}
    for current_score in current["element_scores"]:
        baseline_score = baseline_index.get(current_score["element_id"], {})
        writer(_format_element_row(current_score, baseline_score))


def compare_command(args: argparse.Namespace, writer: Writer = default_writer) -> int:
    """Execute the ``compare`` subcommand."""
    baseline = _load_report_payload(args.baseline)
    current = _load_report_payload(args.current)
    writer(_format_report_header("Baseline", baseline))
    writer(_format_report_header("Current ", current))
    _print_compare_table(baseline, current, writer)
    return 0
