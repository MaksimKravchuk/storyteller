"""Write scenario reports to ``benchmarks/results/`` with reproducibility meta."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from benchmarks.harness._archive_naming import file_stem
from benchmarks.harness._serialise import report_to_serialisable
from benchmarks.harness.report import render_markdown
from benchmarks.harness.types._scores import ScenarioReport

_RESULTS_DIR_NAME = "results"
_ENCODING = "utf-8"


def results_dir() -> Path:
    """Return the archive directory, creating it on first access."""
    package_root = Path(__file__).resolve().parent.parent
    archive_path = package_root / _RESULTS_DIR_NAME
    archive_path.mkdir(parents=True, exist_ok=True)
    return archive_path


def write_pair(stem: str, payload: Any, markdown: str) -> tuple[Path, Path]:
    """Persist a sibling ``<stem>.json`` + ``<stem>.md`` pair under ``results_dir``."""
    base = results_dir() / stem
    json_path = base.with_suffix(".json")
    md_path = base.with_suffix(".md")
    json_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False),
        encoding=_ENCODING,
    )
    md_path.write_text(markdown, encoding=_ENCODING)
    return json_path, md_path


def write_report(report: ScenarioReport) -> tuple[Path, Path]:
    """Persist both JSON + markdown artefacts. Returns their paths."""
    return write_pair(file_stem(report), report_to_serialisable(report), render_markdown(report))


def current_git_sha() -> str:
    """Return ``git rev-parse HEAD`` for the checkout; empty string when git or the repo is unavailable."""
    try:
        done = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parent,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return ""
    return done.stdout.strip()
