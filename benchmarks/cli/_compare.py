"""Implementation of the ``benchmarks compare`` subcommand."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from benchmarks.cli._compare_format import (
    format_element_row,
    format_header,
    format_scenario_classification,
    format_table_header,
)
from benchmarks.cli._writer import Writer, default_writer


def _load_report_payload(path: str) -> dict:
    """Read a JSON report from disk, raising a friendly error on miss."""
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError("Report not found: {0}".format(path))
    try:
        return json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("Report at {0} is not valid JSON: {1}".format(path, exc)) from exc


def _as_aggregate(payload: dict, path: str) -> dict:
    """Reject per-iteration JSON with a helpful message — compare is aggregate-only."""
    if "element_pass_rates" not in payload or "mean_awarded" not in payload:
        raise ValueError(
            "Report at {0} is a per-iteration artefact; pass the *_aggregate.json file".format(path),
        )
    return payload


def _print_compare_table(baseline: dict, current: dict, writer: Writer) -> None:
    """Print the per-element pass-rate table."""
    writer(format_table_header())
    baseline_index = {rate["element_id"]: rate for rate in baseline["element_pass_rates"]}
    for current_rate in current["element_pass_rates"]:
        baseline_rate = baseline_index.get(current_rate["element_id"], {})
        writer(format_element_row(baseline_rate, current_rate))


def compare_command(args: argparse.Namespace, writer: Writer = default_writer) -> int:
    """Execute the ``compare`` subcommand."""
    baseline = _as_aggregate(_load_report_payload(args.baseline), args.baseline)
    current = _as_aggregate(_load_report_payload(args.current), args.current)
    writer(format_header("Baseline", baseline))
    writer(format_header("Current ", current))
    writer(format_scenario_classification(baseline, current))
    _print_compare_table(baseline, current, writer)
    return 0
