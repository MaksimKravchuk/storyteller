"""E2E test: drive a 10-turn session and grade its narrative quality.

Soft report only — the test passes as long as the judge returns valid
JSON scores for all six rubrics. The markdown report is printed to
stdout, attached to Allure, and written to ``allure-results/`` so a CI
workflow can pick it up for a PR comment.
"""

import json
import pathlib
import sys

import allure

from tests.e2e.narrative_report import NarrativeReport, render_markdown_report
from tests.e2e.narrative_session_driver import play_session
from tests.e2e.narrative_test_agent import NarrativeTestAgent

_EXPECTED_RUBRIC_COUNT = 6
_MIN_VALID_SCORE = 1
_MAX_VALID_SCORE = 10
_AVERAGE_PRECISION = 2

_PROJECT_ROOT = pathlib.Path(__file__).parents[2]
_ARTIFACT_PATHS: tuple[pathlib.Path, ...] = (
    _PROJECT_ROOT / "allure-results" / "narrative-report.md",
    _PROJECT_ROOT / "tests" / "e2e" / ".last-narrative-report.md",
)


@allure.feature("Narrative Quality")
@allure.story("End-to-end Evaluation")
@allure.severity(allure.severity_level.NORMAL)
def test_narrative_quality(game_process):
    judge = NarrativeTestAgent()
    transcript = play_session(game_process)
    report = judge.evaluate_session(transcript)
    _publish_report(report, transcript.setting)
    _assert_report_shape(report)


def _publish_report(report: NarrativeReport, setting: str) -> None:
    markdown = render_markdown_report(report, setting)
    sys.stdout.write(f"{markdown}\n")
    sys.stdout.flush()
    allure.attach(
        markdown,
        name="narrative-report.md",
        attachment_type=allure.attachment_type.TEXT,
    )
    allure.attach(
        json.dumps(_report_to_dict(report), indent=2),
        name="narrative-scores",
        attachment_type=allure.attachment_type.JSON,
    )
    _write_artifact(markdown)


def _report_to_dict(report: NarrativeReport) -> dict:
    return {
        "model": report.model,
        "average": round(report.average, _AVERAGE_PRECISION),
        "scores": [
            {
                "rubric": rs.rubric,
                "score": rs.score,
                "reasoning": rs.reasoning,
                "issues": list(rs.issues),
            }
            for rs in report.scores
        ],
    }


def _write_artifact(markdown: str) -> None:
    for target_path in _ARTIFACT_PATHS:
        try:
            _write_artifact_file(target_path, markdown)
        except OSError as exc:
            _attach_artifact_error(target_path, exc)


def _write_artifact_file(target_path: pathlib.Path, markdown: str) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(markdown, encoding="utf-8")


def _attach_artifact_error(target_path: pathlib.Path, exc: OSError) -> None:
    reason = str(exc)
    body = f"Failed to write {target_path}: {reason}"
    leaf = target_path.name
    allure.attach(
        body,
        name=f"artifact-error-{leaf}",
        attachment_type=allure.attachment_type.TEXT,
    )


def _assert_report_shape(report: NarrativeReport) -> None:
    assert len(report.scores) == _EXPECTED_RUBRIC_COUNT
    for rubric_score in report.scores:
        assert _MIN_VALID_SCORE <= rubric_score.score <= _MAX_VALID_SCORE
