"""Implementation of the ``benchmarks compare`` subcommand."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from benchmarks.cli._bayes_format import format_scenario_block
from benchmarks.cli._compare_format import (
    format_element_row,
    format_header,
    format_scenario_classification,
    format_table_header,
)
from benchmarks.harness.bayes._report import verdict_for_scenario


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


def _write(line: str) -> None:
    sys.stdout.write("{0}\n".format(line))


def _print_compare_table(baseline: dict, current: dict) -> None:
    """Print the per-element pass-rate table."""
    _write(format_table_header())
    baseline_index = {rate["element_id"]: rate for rate in baseline["element_pass_rates"]}
    for current_rate in current["element_pass_rates"]:
        baseline_rate = baseline_index.get(current_rate["element_id"], {})
        _write(format_element_row(baseline_rate, current_rate))


def _print_bayes_verdict(baseline: dict, current: dict) -> None:
    """Print the graded Bayesian verdict beneath the frequentist banner.

    The jq-extracted aggregate carries no separate noise floor, so the baseline's
    own descriptive stdev stands in as the run-to-run noise scale.
    """
    verdict = verdict_for_scenario(
        baseline,
        current,
        noise_floor_stdev=baseline.get("stdev_awarded", float(0)),
    )
    for line in format_scenario_block(verdict):
        _write(line)


def compare_command(args: argparse.Namespace) -> int:
    """Execute the ``compare`` subcommand."""
    baseline = _as_aggregate(_load_report_payload(args.baseline), args.baseline)
    current = _as_aggregate(_load_report_payload(args.current), args.current)
    _write(format_header("Baseline", baseline))
    _write(format_header("Current ", current))
    _write(format_scenario_classification(baseline, current))
    _print_bayes_verdict(baseline, current)
    _print_compare_table(baseline, current)
    return 0
