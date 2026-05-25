"""Tests for the ``benchmarks reliability-report`` CLI command."""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

import allure
import pytest

from benchmarks.cli import _main, _reliability_report, _reliability_table

pytestmark = [
    allure.epic("Engine & LLM Infrastructure"),
    allure.feature("Reliability metering"),
]


def _write_iteration(tmp_path: Path, name: str, reliability_counts: dict) -> Path:
    """Persist a fake per-iteration JSON archive containing only the relevant fields."""
    payload = {
        "scenario_id": "fake",
        "iteration": 0,
        "reliability_counts": reliability_counts,
    }
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_aggregate(tmp_path: Path, name: str) -> Path:
    """Persist a fake aggregate archive (no reliability_counts, has element_pass_rates)."""
    payload = {
        "scenario_id": "fake",
        "element_pass_rates": [],
        "mean_awarded": 0,
    }
    path = tmp_path / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


@allure.story("Aggregation")
@allure.title("aggregate_counts sums per-iteration counters by (agent, event_type)")
def test_aggregate_counts_sums_iterations(tmp_path: Path) -> None:
    _write_iteration(
        tmp_path,
        "iter0.json",
        {"dramaturge": {"silent_fallback": 2}, "Director": {"validation_retry": 1}},
    )
    _write_iteration(
        tmp_path,
        "iter1.json",
        {"dramaturge": {"silent_fallback": 3}, "narrator": {"silent_fallback": 1}},
    )

    totals = _reliability_report.aggregate_counts(tmp_path)

    assert totals == {
        ("Director", "validation_retry"): 1,
        ("dramaturge", "silent_fallback"): 5,
        ("narrator", "silent_fallback"): 1,
    }


@allure.story("Aggregation")
@allure.title("aggregate_counts skips aggregate archives mixed into the directory")
def test_aggregate_counts_skips_aggregate_archives(tmp_path: Path) -> None:
    _write_iteration(tmp_path, "iter0.json", {"narrator": {"silent_fallback": 4}})
    _write_aggregate(tmp_path, "scenario_aggregate.json")

    totals = _reliability_report.aggregate_counts(tmp_path)

    assert totals == {("narrator", "silent_fallback"): 4}


@allure.story("Aggregation")
@allure.title("aggregate_counts accepts a single-file path")
def test_aggregate_counts_accepts_single_file(tmp_path: Path) -> None:
    single = _write_iteration(tmp_path, "iter0.json", {"data_miner": {"silent_fallback": 2}})

    totals = _reliability_report.aggregate_counts(single)

    assert totals == {("data_miner", "silent_fallback"): 2}


@allure.story("Aggregation")
@allure.title("aggregate_counts returns {} for a directory with no per-iteration archives")
def test_aggregate_counts_empty_directory(tmp_path: Path) -> None:
    _write_aggregate(tmp_path, "scenario_aggregate.json")

    assert _reliability_report.aggregate_counts(tmp_path) == {}


@allure.story("Aggregation")
@allure.title("aggregate_counts skips non-suffixed archives carrying element_pass_rates")
def test_aggregate_counts_skips_aggregate_payload_in_unsuffixed_file(tmp_path: Path) -> None:
    """If a directory holds a payload with ``element_pass_rates`` but a non-aggregate name."""
    path = tmp_path / "iter0.json"
    path.write_text(
        json.dumps({"element_pass_rates": [], "reliability_counts": {"x": {"silent_fallback": 9}}}),
        encoding="utf-8",
    )

    assert _reliability_report.aggregate_counts(tmp_path) == {}


@allure.story("Aggregation")
@allure.title("aggregate_counts tolerates malformed nested-dict entries")
def test_aggregate_counts_tolerates_non_dict_blob(tmp_path: Path) -> None:
    path = tmp_path / "iter0.json"
    path.write_text(
        json.dumps({"reliability_counts": {"narrator": "broken", "dramaturge": {"silent_fallback": 2}}}),
        encoding="utf-8",
    )

    assert _reliability_report.aggregate_counts(tmp_path) == {("dramaturge", "silent_fallback"): 2}


@allure.story("Table formatting")
@allure.title("format_table prints headers and rows in (agent, event_type) order")
def test_format_table_sorted_rows() -> None:
    rendered = _reliability_table.format_table(
        {
            ("narrator", "silent_fallback"): 1,
            ("dramaturge", "silent_fallback"): 5,
            ("Director", "validation_retry"): 3,
        },
    )

    lines = rendered.splitlines()
    assert lines[0].startswith("agent")
    assert "Director" in lines[2]
    assert "dramaturge" in lines[3]
    assert "narrator" in lines[4]
    assert lines[2].strip().endswith("3")
    assert lines[3].strip().endswith("5")
    assert lines[4].strip().endswith("1")


@allure.story("Table formatting")
@allure.title("format_table renders an empty-state line when counters are empty")
def test_format_table_empty_state() -> None:
    rendered = _reliability_table.format_table({})

    assert rendered == "(no reliability counters found)"


@allure.story("CLI dispatch")
@allure.title("reliability-report subcommand prints the aggregated table to stdout")
def test_cli_prints_table(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_iteration(tmp_path, "iter0.json", {"dramaturge": {"silent_fallback": 2}})
    captured = io.StringIO()
    monkeypatch.setattr(sys, "stdout", captured)

    exit_code = _main.main(["reliability-report", str(tmp_path)])

    assert exit_code == 0
    output = captured.getvalue()
    assert "dramaturge" in output
    assert "silent_fallback" in output
    assert "2" in output


@allure.story("CLI dispatch")
@allure.title("reliability-report exits 2 when the target path is missing")
def test_cli_missing_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    captured = io.StringIO()
    monkeypatch.setattr(sys, "stderr", captured)
    args = argparse.Namespace(path=str(tmp_path / "no-such-file.json"))

    exit_code = _reliability_report.reliability_report_command(args)

    assert exit_code == 2
    assert "Path not found" in captured.getvalue()
