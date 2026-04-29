"""Unit tests for archive I/O helpers — file_stem, write_report, read_head_sha."""

from __future__ import annotations

import json
from pathlib import Path

import allure

from benchmarks.harness._archive_naming import file_stem
from benchmarks.harness._git_sha import read_head_sha
from benchmarks.harness.archive import write_report
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
class TestReadHeadSha:
    @allure.story("Archive metadata")
    @allure.title("read_head_sha returns a direct detached-HEAD sha with surrounding whitespace stripped")
    def test_detached_head_returned_verbatim(self, tmp_path: Path):
        head = tmp_path / "HEAD"
        head.write_text("deadbeef1234567890\n", encoding="utf-8")

        assert read_head_sha(head) == "deadbeef1234567890"

    @allure.story("Archive metadata")
    @allure.title("read_head_sha follows a 'ref:' HEAD into a loose-ref file inside the git directory")
    def test_loose_ref_followed(self, tmp_path: Path):
        head = tmp_path / "HEAD"
        head.write_text("ref: refs/heads/main\n", encoding="utf-8")
        loose = tmp_path / "refs" / "heads" / "main"
        loose.parent.mkdir(parents=True)
        loose.write_text("abc123\n", encoding="utf-8")

        assert read_head_sha(head) == "abc123"

    @allure.story("Archive metadata")
    @allure.title("read_head_sha falls back to the packed-refs file when no loose ref exists for the branch")
    def test_packed_ref_fallback(self, tmp_path: Path):
        head = tmp_path / "HEAD"
        head.write_text("ref: refs/heads/main\n", encoding="utf-8")
        packed = tmp_path / "packed-refs"
        packed.write_text(
            "# pack-refs with: peeled fully-peeled sorted\naaaa1111bbbb2222cccc3333dddd4444eeee5555 refs/heads/main\n",
            encoding="utf-8",
        )

        assert read_head_sha(head) == "aaaa1111bbbb2222cccc3333dddd4444eeee5555"

    @allure.story("Archive metadata")
    @allure.title("read_head_sha returns the empty string when the HEAD file does not exist")
    def test_missing_head_returns_empty(self, tmp_path: Path):
        assert read_head_sha(tmp_path / "does-not-exist" / "HEAD") == ""
