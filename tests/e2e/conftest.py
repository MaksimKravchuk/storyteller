"""E2E test fixtures."""

import os
import pathlib
import subprocess
import sys

import pytest
from loguru import logger

from log_scrubbing import install_scrubber
from tests.e2e.log_capture import (
    GAME_PROCESS_LOG,
    GAME_STDERR_LOG,
    TEST_SESSION_LOG,
    LogLayout,
    StderrDrainer,
    finalize_log_artifacts,
    read_stderr_fallback,
    terminate_game_process,
)

PROJECT_ROOT = pathlib.Path(__file__).parents[2]
MAIN_PY = str(PROJECT_ROOT / "main.py")
GAME_START_TIMEOUT = 120
ACTION_TIMEOUT = 90
SETTING = "Ancient Rome, 1st century AD"

_TEST_LOG_FORMAT = "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name} | {message}"


def assert_process_alive(proc) -> None:
    """Fail the test with captured stderr if the game process has exited."""
    rc = proc.poll()
    if rc is None:
        return
    stderr_output = read_stderr_fallback(proc)
    pytest.fail(f"Game process exited unexpectedly (code {rc}).\nStderr:\n{stderr_output}")


@pytest.fixture(autouse=True, scope="session")
def _e2e_log_capture():
    """Session-scoped loguru file sink + scrubber + final artifact scrub.

    - installs the shared secret scrubber once for the pytest process
    - adds a loguru file sink at ``allure-results/logs/test-session.log``
    - on teardown removes the sink, runs a belt-and-suspenders scrub
      pass over every captured log file (subprocess + stderr + session),
      and attaches each scrubbed file to Allure for the HTML report
    """
    install_scrubber()
    layout = LogLayout(root=PROJECT_ROOT)
    layout.ensure()
    test_log_path = layout.path_for(TEST_SESSION_LOG)
    sink_id = logger.add(
        str(test_log_path),
        level="INFO",
        format=_TEST_LOG_FORMAT,
        enqueue=True,
        backtrace=False,
        diagnose=False,
    )
    try:
        yield
    finally:
        logger.remove(sink_id)
        finalize_log_artifacts(PROJECT_ROOT)


@pytest.fixture()
def game_process():
    layout = LogLayout(root=PROJECT_ROOT)
    layout.ensure()
    env = _build_game_env(layout)
    proc = _spawn_game(env)
    drainer = StderrDrainer.attach_to(proc, layout.path_for(GAME_STDERR_LOG))
    try:
        yield proc
    finally:
        terminate_game_process(proc)
        drainer.stop_and_join()


def _build_game_env(layout: LogLayout) -> dict:
    env = os.environ.copy()
    has_llm_key = env.get("OPENAI_API_KEY") or env.get("ANTHROPIC_API_KEY")
    if not has_llm_key:
        pytest.skip("No LLM API keys — skipping e2e tests")
    env["STORYTELLER_LOG_FILE"] = str(layout.path_for(GAME_PROCESS_LOG))
    return env


def _spawn_game(env: dict) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, MAIN_PY],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
