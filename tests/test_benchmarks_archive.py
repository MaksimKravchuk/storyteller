"""Unit tests for archive I/O helpers — file_stem, write_report, git_sha."""

from __future__ import annotations

import json
import subprocess
from unittest import mock

import allure
import pytest

from benchmarks.harness._archive_naming import file_stem
from benchmarks.harness.archive import current_git_sha, write_report
from benchmarks.harness.types._scores import (
    ElementScore,
    PanelMember,
    ScenarioReport,
    SkippedCandidate,
)


def _report(**overrides) -> ScenarioReport:
    """Build a minimal :class:`ScenarioReport` with overridable fields."""
    defaults = {
        "scenario_id": "memory_follow_up_marcus",
        "scenario_label": "Memory follow-up",
        "iteration": 0,
        "total_base": 1,
        "total_awarded": 1,
        "element_scores": [
            ElementScore(
                element_id="e1",
                label="e1",
                kind="deterministic",
                base_value=1,
                awarded=1,
                reason="ok",
            ),
        ],
        "captured_turns": [],
        "panel": [PanelMember(provider="openai", model_id="gpt-x")],
        "skipped_panel_candidates": [
            SkippedCandidate(alias="opus", provider="anthropic", model_id="opus-4", reason="no key"),
        ],
        "engine_git_sha": "abc1234deadbeef",
        "engine_models": {"director_model": "a", "agent_model": "b", "narrator_model": "c"},
        "started_at": "2025-01-02T03:04:05",
        "duration_seconds": 1.5,
    }
    defaults.update(overrides)
    return ScenarioReport(**defaults)  # type: ignore[arg-type]


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestFileStem:
    @allure.story("Archive naming")
    @allure.title("file_stem builds <timestamp>_<short-sha>_<scenario>_iter<N> from the report metadata")
    def test_happy_path_stem(self):
        stem = file_stem(_report(started_at="2025-01-02T03:04:05"))

        assert stem == "2025-01-02T03-04-05_abc1234_memory_follow_up_marcus_iter0"

    @allure.story("Archive naming")
    @allure.title("file_stem falls back to 'nosha' when the engine_git_sha field is empty")
    def test_missing_sha_uses_nosha(self):
        stem = file_stem(_report(started_at="2025-01-02T03:04:05", engine_git_sha=""))

        assert "nosha" in stem

    @allure.story("Archive naming")
    @allure.title("file_stem sanitises filesystem-hostile characters in scenario ids")
    def test_scenario_id_sanitised(self):
        stem = file_stem(_report(started_at="2025-01-02T03:04:05", scenario_id="a/b:c"))

        assert "a_b_c" in stem
        assert "/" not in stem
        assert ":" not in stem


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestWriteReport:
    @allure.story("Archive I/O")
    @allure.title("write_report writes matching .json and .md artefacts into the results directory")
    def test_writes_both_files(self, tmp_path, monkeypatch):
        monkeypatch.setattr("benchmarks.harness.archive.results_dir", lambda: tmp_path)
        report = _report()

        json_path, md_path = write_report(report)

        assert json_path.is_file()
        assert md_path.is_file()
        assert json_path.suffix == ".json"
        assert md_path.suffix == ".md"
        assert json_path.stem == md_path.stem

    @allure.story("Archive I/O")
    @allure.title("write_report emits a JSON artefact whose element scores round-trip through json.loads")
    def test_json_artefact_roundtrips(self, tmp_path, monkeypatch):
        monkeypatch.setattr("benchmarks.harness.archive.results_dir", lambda: tmp_path)

        json_path, _ = write_report(_report())

        payload = json.loads(json_path.read_text(encoding="utf-8"))
        assert payload["scenario_id"] == "memory_follow_up_marcus"
        assert payload["element_scores"][0]["element_id"] == "e1"
        assert payload["skipped_panel_candidates"][0]["alias"] == "opus"


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Benchmark harness")
class TestCurrentGitSha:
    @allure.story("Archive metadata")
    @allure.title("current_git_sha returns the empty string when git is not installed")
    def test_missing_git_returns_empty(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(subprocess, "run", mock.Mock(side_effect=FileNotFoundError))

        assert current_git_sha() == ""

    @allure.story("Archive metadata")
    @allure.title("current_git_sha returns the stripped stdout of git rev-parse HEAD")
    def test_returns_stripped_sha(self, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(subprocess, "run", mock.Mock(return_value=mock.Mock(stdout="abc123\n")))

        assert current_git_sha() == "abc123"
