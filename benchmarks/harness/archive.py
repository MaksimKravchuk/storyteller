"""Write scenario reports to ``benchmarks/results/`` with reproducibility meta.

Each run produces two files with the same stem:
``<timestamp>_<git-sha>_<scenario>_<iter>.{json,md}``. The JSON is the
machine-readable artefact (consumed by the ``compare`` subcommand); the
markdown is what a reviewer opens in a PR.

The directory is resolved relative to the repository root so the archive
layout is stable across ``uv run`` invocations from any subdirectory.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from benchmarks.harness._archive_naming import file_stem
from benchmarks.harness._git_sha import read_head_sha
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


def write_report(report: ScenarioReport) -> tuple[Path, Path]:
    """Persist both JSON + markdown artefacts. Returns their paths."""
    base = results_dir() / file_stem(report)
    json_path = base.with_suffix(".json")
    md_path = base.with_suffix(".md")
    json_path.write_text(
        json.dumps(report_to_serialisable(report), indent=2, sort_keys=True, ensure_ascii=False),
        encoding=_ENCODING,
    )
    md_path.write_text(render_markdown(report), encoding=_ENCODING)
    return json_path, md_path


def current_git_sha() -> str:
    """Read ``HEAD`` without shelling out, so the harness runs offline.

    Falls back to the empty string when we are not inside a working
    tree with a readable ``HEAD`` (tarballs, containers with a stripped
    ``.git``, etc.) — the sha is metadata, not a hard requirement.
    """
    head_file = Path(__file__).resolve().parent.parent.parent / ".git" / "HEAD"
    if not head_file.is_file():
        return ""
    return read_head_sha(head_file)


def environment_signature() -> dict[str, str]:
    """Return minimal machine-identifying metadata for the run artefact."""
    return {
        "cwd": os.getcwd(),
        "python_version": os.environ.get("PYTHON_VERSION", ""),
    }
