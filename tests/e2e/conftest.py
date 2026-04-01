"""E2E test fixtures."""

import os
import pathlib
import subprocess
import sys

import pytest

MAIN_PY = str(pathlib.Path(__file__).parents[2] / "main.py")
GAME_START_TIMEOUT = 120
ACTION_TIMEOUT = 90
SETTING = "Ancient Rome, 1st century AD"


def assert_process_alive(proc) -> None:
    """Fail the test with stderr output if the game process has exited."""
    rc = proc.poll()
    if rc is not None:
        stderr_output = proc.stderr.read().decode("utf-8", errors="replace")
        pytest.fail(f"Game process exited unexpectedly (code {rc}).\nStderr:\n{stderr_output}")


def _send_quit(proc) -> None:
    """Send quit command to the subprocess stdin."""
    proc.stdin.write(b"quit\n")
    proc.stdin.flush()


@pytest.fixture()
def game_process():
    env = os.environ.copy()
    if not env.get("OPENAI_API_KEY") and not env.get("ANTHROPIC_API_KEY"):
        pytest.skip("No LLM API keys — skipping e2e tests")
    proc = subprocess.Popen(
        [sys.executable, MAIN_PY],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    yield proc
    if proc.poll() is None:
        try:
            _send_quit(proc)
        except BrokenPipeError:
            ...
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
