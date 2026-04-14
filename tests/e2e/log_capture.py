"""Log capture helpers for e2e narrative-quality runs.

Separated from ``conftest.py`` so that module stays within the WPS
module-member limit. This file holds:

- :class:`LogLayout`, the path resolver for the captured artifacts
- :class:`StderrDrainer`, a daemon thread that continuously drains a
  subprocess stderr pipe into a file so the pipe buffer never blocks
- :func:`scrub_file_in_place`, a belt-and-suspenders pass that reruns
  the shared secret scrubber over each log file before upload
- :func:`read_stderr_fallback` / :func:`terminate_game_process` /
  :func:`finalize_log_artifacts` — helpers invoked by the fixtures in
  ``conftest.py``
"""

from __future__ import annotations

import contextlib
import os
import pathlib
import select
import subprocess
import threading
from dataclasses import dataclass

import allure

from log_scrubbing import scrub_secrets

_DRAIN_POLL_INTERVAL = 0.1
_DRAIN_CHUNK_SIZE = 4096
_STDERR_JOIN_TIMEOUT = 2.0
_PROCESS_WAIT_TIMEOUT = 5
_TEXT_ENCODING = "utf-8"
_DECODE_ERRORS = "replace"

_ARTIFACT_DIR = pathlib.Path("allure-results") / "logs"

GAME_PROCESS_LOG = _ARTIFACT_DIR / "game-process.log"
GAME_STDERR_LOG = _ARTIFACT_DIR / "game-process.stderr.log"
TEST_SESSION_LOG = _ARTIFACT_DIR / "test-session.log"

LOG_PATHS: tuple[pathlib.Path, ...] = (
    GAME_PROCESS_LOG,
    GAME_STDERR_LOG,
    TEST_SESSION_LOG,
)


@dataclass(frozen=True)
class LogLayout:
    """Resolve absolute log-artifact paths relative to a project root."""

    root: pathlib.Path

    def ensure(self) -> pathlib.Path:
        """Create ``<root>/allure-results/logs`` and return the absolute path."""
        absolute = (self.root / _ARTIFACT_DIR).resolve()
        absolute.mkdir(parents=True, exist_ok=True)
        return absolute

    def path_for(self, relative: pathlib.Path) -> pathlib.Path:
        """Return the absolute location of ``relative`` under the project root."""
        return (self.root / relative).resolve()


class StderrDrainer(threading.Thread):
    """Background thread that streams a pipe fd into a file on disk.

    Runs as a daemon so test teardown never hangs. ``stop()`` signals the
    loop to exit at the next poll tick; the thread also exits naturally
    when the underlying file descriptor closes.
    """

    def __init__(self, fd: int, output_path: pathlib.Path) -> None:
        super().__init__(name="stderr-drainer", daemon=True)
        self._fd = fd
        self._output_path = output_path
        self._stop_event = threading.Event()

    @classmethod
    def attach_to(cls, proc, stderr_log_path: pathlib.Path) -> StderrDrainer:
        """Start a drainer for ``proc`` and record it on the Popen object."""
        drainer = cls(proc.stderr.fileno(), stderr_log_path)
        drainer.start()
        proc.stderr_log_path = stderr_log_path  # type: ignore[attr-defined]
        proc.stderr_drainer = drainer  # type: ignore[attr-defined]
        return drainer

    def run(self) -> None:
        output_path = self._output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("ab") as sink:
            self._drain_loop(sink)

    def stop(self) -> None:
        self._stop_event.set()

    def stop_and_join(self) -> None:
        """Signal the drainer to stop and wait up to the join timeout."""
        self.stop()
        self.join(timeout=_STDERR_JOIN_TIMEOUT)

    def _drain_loop(self, sink) -> None:
        while not self._stop_event.is_set():
            if not self._poll_and_copy(sink):
                return

    def _poll_and_copy(self, sink) -> bool:
        ready, _, _ = select.select([self._fd], [], [], _DRAIN_POLL_INTERVAL)
        if not ready:
            return True
        try:
            chunk = os.read(self._fd, _DRAIN_CHUNK_SIZE)
        except OSError:
            return False
        if not chunk:
            return False
        sink.write(chunk)
        sink.flush()
        return True


def scrub_file_in_place(path: pathlib.Path) -> None:
    """Run :func:`scrub_secrets` over ``path`` and rewrite it atomically.

    A belt-and-suspenders pass that catches anything the loguru patcher
    could not reach — third-party libraries writing directly to stderr,
    exception tracebacks, and so on. Missing files are ignored so the
    fixture teardown is robust when the test skipped or failed early.
    """
    if path.exists():
        raw = path.read_text(encoding=_TEXT_ENCODING, errors=_DECODE_ERRORS)
        path.write_text(scrub_secrets(raw), encoding=_TEXT_ENCODING)


def read_stderr_fallback(proc) -> str:
    """Return the captured stderr tail for a dead process.

    When the stderr drainer thread is attached, the pipe has already
    been consumed — reading from it would yield an empty string. Read
    from the captured log file instead so we still surface whatever
    crashed the subprocess.
    """
    stderr_path: pathlib.Path | None = getattr(proc, "stderr_log_path", None)
    if stderr_path and stderr_path.exists():
        return stderr_path.read_text(encoding=_TEXT_ENCODING, errors=_DECODE_ERRORS)
    raw = b"" if proc.stderr is None else proc.stderr.read()
    return raw.decode(_TEXT_ENCODING, errors=_DECODE_ERRORS)


def terminate_game_process(proc) -> None:
    """Gracefully close a running game subprocess, force-killing on timeout."""
    if proc.poll() is not None:
        return
    with contextlib.suppress(BrokenPipeError):
        proc.stdin.write(b"quit\n")
        proc.stdin.flush()
    try:
        proc.wait(timeout=_PROCESS_WAIT_TIMEOUT)
    except subprocess.TimeoutExpired:
        proc.kill()


def finalize_log_artifacts(root: pathlib.Path) -> None:
    """Run a final scrub pass over each captured log and attach it to Allure."""
    layout = LogLayout(root=root)
    for relative_path in LOG_PATHS:
        absolute = layout.path_for(relative_path)
        scrub_file_in_place(absolute)
        _attach_log(relative_path.name, absolute)


def _attach_log(name: str, path: pathlib.Path) -> None:
    if path.exists():
        allure.attach(
            path.read_text(encoding=_TEXT_ENCODING, errors=_DECODE_ERRORS),
            name=name,
            attachment_type=allure.attachment_type.TEXT,
        )
