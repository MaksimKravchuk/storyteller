"""Unit tests for the ``benchmarks narration-diff`` subcommand."""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

import allure
import pytest

from benchmarks.cli import _main, _narration_diff
from benchmarks.cli._narration_diff_format import format_report
from benchmarks.cli._narration_diff_model import TurnText

pytestmark = [
    allure.epic("Engine & LLM Infrastructure"),
    allure.feature("Benchmark harness"),
]

_TurnSpec = tuple[int, str, str]


def _write_iteration(
    directory: Path,
    name: str,
    scenario_id: str,
    turns: list[_TurnSpec],
) -> Path:
    """Persist a per-iteration archive carrying only scenario id + captured turns."""
    payload = {
        "scenario_id": scenario_id,
        "iteration": 0,
        "captured_turns": [
            {"index": index, "player_action": action, "narration": narration} for index, action, narration in turns
        ],
    }
    path = directory / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_aggregate(directory: Path, name: str, scenario_id: str) -> Path:
    """Persist an aggregate archive (carries element_pass_rates, no captured_turns)."""
    payload = {"scenario_id": scenario_id, "element_pass_rates": [], "mean_awarded": 0}
    path = directory / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


@allure.story("Narration diff")
@allure.title("build_turn_index maps scenario id to its captured turns")
def test_build_turn_index_extracts_turns(tmp_path: Path) -> None:
    _write_iteration(tmp_path, "a_iter0.json", "scene_a", [(0, "look", "A dim hall.")])

    index = _narration_diff.build_turn_index(tmp_path)

    assert index == {"scene_a": [TurnText(index=0, player_action="look", narration="A dim hall.")]}


@allure.story("Narration diff")
@allure.title("build_turn_index keeps the first iteration seen per scenario")
def test_build_turn_index_first_iteration_wins(tmp_path: Path) -> None:
    _write_iteration(tmp_path, "a_iter0.json", "scene_a", [(0, "look", "first")])
    _write_iteration(tmp_path, "b_iter1.json", "scene_a", [(0, "look", "second")])

    index = _narration_diff.build_turn_index(tmp_path)

    assert index["scene_a"][0].narration == "first"


@allure.story("Narration diff")
@allure.title("build_turn_index skips aggregate archives")
def test_build_turn_index_skips_aggregates(tmp_path: Path) -> None:
    _write_aggregate(tmp_path, "scene_a_aggregate.json", "scene_a")

    assert _narration_diff.build_turn_index(tmp_path) == {}


@allure.story("Narration diff")
@allure.title("build_turn_index skips a per-iteration archive missing its scenario id")
def test_build_turn_index_skips_missing_scenario_id(tmp_path: Path) -> None:
    path = tmp_path / "broken_iter0.json"
    path.write_text(json.dumps({"captured_turns": [{"index": 0}]}), encoding="utf-8")

    assert _narration_diff.build_turn_index(tmp_path) == {}


@allure.story("Narration diff")
@allure.title("build_turn_index skips an aggregate-shaped payload with a non-aggregate name")
def test_build_turn_index_skips_unsuffixed_aggregate(tmp_path: Path) -> None:
    path = tmp_path / "scene_a_iter0.json"
    path.write_text(
        json.dumps({"scenario_id": "scene_a", "element_pass_rates": []}),
        encoding="utf-8",
    )

    assert _narration_diff.build_turn_index(tmp_path) == {}


@allure.story("Narration diff")
@allure.title("format_report flags an unchanged turn")
def test_format_report_unchanged_turn() -> None:
    turns = [TurnText(index=0, player_action="look", narration="same")]

    report = format_report({"scene_a": turns}, {"scene_a": turns})

    assert "_unchanged_" in report
    assert "_previous:_" not in report


@allure.story("Narration diff")
@allure.title("format_report shows previous + current blockquotes for a changed turn")
def test_format_report_changed_turn() -> None:
    previous = {"scene_a": [TurnText(index=0, player_action="look", narration="old prose")]}
    current = {"scene_a": [TurnText(index=0, player_action="look", narration="new prose")]}

    report = format_report(previous, current)

    assert "_previous:_" in report
    assert "> old prose" in report
    assert "_current:_" in report
    assert "> new prose" in report


@allure.story("Narration diff")
@allure.title("format_report notes a new scenario absent from the baseline")
def test_format_report_new_scenario() -> None:
    previous = {"scene_a": [TurnText(index=0, player_action="look", narration="x")]}
    current = {"scene_b": [TurnText(index=0, player_action="move", narration="y")]}

    report = format_report(previous, current)

    assert "### scene_b" in report
    assert "_New scenario — no prior version to compare._" in report


@allure.story("Narration diff")
@allure.title("format_report emits the no-baseline banner once when previous is empty")
def test_format_report_no_baseline() -> None:
    current = {"scene_a": [TurnText(index=0, player_action="look", narration="y")]}

    report = format_report({}, current)

    assert "_No baseline content available — first run or no prior artifact._" in report
    assert "_New scenario" not in report
    assert "_no prior turn at this index_" in report


@allure.story("Narration diff")
@allure.title("format_report notes a current turn with no prior counterpart")
def test_format_report_new_turn_index() -> None:
    previous = {"scene_a": [TurnText(index=0, player_action="look", narration="x")]}
    current = {
        "scene_a": [
            TurnText(index=0, player_action="look", narration="x"),
            TurnText(index=1, player_action="move", narration="z"),
        ],
    }

    report = format_report(previous, current)

    assert "_no prior turn at this index_" in report


@allure.story("Narration diff")
@allure.title("format_report notes a turn that exists only in the previous version")
def test_format_report_removed_turn() -> None:
    previous = {
        "scene_a": [
            TurnText(index=0, player_action="look", narration="x"),
            TurnText(index=1, player_action="move", narration="z"),
        ],
    }
    current = {"scene_a": [TurnText(index=0, player_action="look", narration="x")]}

    report = format_report(previous, current)

    assert "_turn 1 present in previous version only_" in report


@allure.story("Narration diff")
@allure.title("format_report blockquotes each line of multi-line narration")
def test_format_report_multiline_blockquote() -> None:
    previous = {"scene_a": [TurnText(index=0, player_action="look", narration="line one\nline two")]}
    current = {"scene_a": [TurnText(index=0, player_action="look", narration="changed")]}

    report = format_report(previous, current)

    assert "> line one" in report
    assert "> line two" in report


@allure.story("Narration diff")
@allure.title("format_report separates the previous and current blockquotes with blank lines")
def test_format_report_separates_previous_and_current_blocks() -> None:
    previous = {"scene_a": [TurnText(index=0, player_action="look", narration="old prose")]}
    current = {"scene_a": [TurnText(index=0, player_action="look", narration="new prose")]}

    report = format_report(previous, current)

    # A blank line must sit between each label and its quote, and between the
    # previous blockquote and the current label — otherwise GitHub-flavoured
    # markdown lazy-continuation merges both narrations into one blockquote.
    assert "_previous:_\n\n> old prose" in report
    assert "> old prose\n\n_current:_\n\n> new prose" in report


@allure.story("Narration diff")
@allure.title("format_report renders the empty-current placeholder")
def test_format_report_empty_current() -> None:
    report = format_report({}, {})

    assert "_No current results found._" in report


@allure.story("CLI dispatch")
@allure.title("narration-diff subcommand prints the report to stdout")
def test_cli_prints_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    previous_dir = tmp_path / "prev"
    current_dir = tmp_path / "cur"
    previous_dir.mkdir()
    current_dir.mkdir()
    _write_iteration(previous_dir, "a_iter0.json", "scene_a", [(0, "look", "old")])
    _write_iteration(current_dir, "a_iter0.json", "scene_a", [(0, "look", "new")])
    captured = io.StringIO()
    monkeypatch.setattr(sys, "stdout", captured)

    exit_code = _main.main(["narration-diff", str(previous_dir), str(current_dir)])

    assert exit_code == 0
    output = captured.getvalue()
    assert "### scene_a" in output
    assert "> old" in output
    assert "> new" in output


@allure.story("CLI dispatch")
@allure.title("narration-diff degrades to a no-baseline report when previous dir is absent")
def test_cli_missing_previous_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    current_dir = tmp_path / "cur"
    current_dir.mkdir()
    _write_iteration(current_dir, "a_iter0.json", "scene_a", [(0, "look", "only")])
    captured = io.StringIO()
    monkeypatch.setattr(sys, "stdout", captured)

    exit_code = _main.main(["narration-diff", str(tmp_path / "missing"), str(current_dir)])

    assert exit_code == 0
    assert "_No baseline content available" in captured.getvalue()


@allure.story("CLI dispatch")
@allure.title("narration-diff exits 2 when the current path is missing")
def test_cli_missing_current_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    captured = io.StringIO()
    monkeypatch.setattr(sys, "stderr", captured)
    args = argparse.Namespace(previous=str(tmp_path), current=str(tmp_path / "no-such-dir"))

    exit_code = _narration_diff.narration_diff_command(args)

    assert exit_code == 2
    assert "Current results path not found" in captured.getvalue()
