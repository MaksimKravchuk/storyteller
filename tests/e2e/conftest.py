"""E2E test fixtures."""

import os
import subprocess
import sys

import pytest

MAIN_PY = "/Users/max/Code/storyteller/main.py"
GAME_START_TIMEOUT = 120
ACTION_TIMEOUT = 90
SETTING = "Ancient Rome, 1st century AD"


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
        proc.stdin.write(b"quit\n")
        proc.stdin.flush()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
