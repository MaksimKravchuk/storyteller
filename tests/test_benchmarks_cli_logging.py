"""The benchmark CLI must not render frame-local secrets into tracebacks (public CI logs)."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Iterator

import allure
import pytest
from loguru import logger

from benchmarks.cli import _main

_SECRET = "sk-proj-{0}".format("C" * 40)
_COMMAND = "leaky"


def _fail_with_secret_local(api_key: str) -> None:
    raise ValueError("boom")


def _leaky_command(_args: argparse.Namespace) -> int:
    try:
        _fail_with_secret_local(_SECRET)
    except ValueError:
        logger.opt(exception=True).error("request failed")
    return 0


@pytest.fixture
def leaky_cli(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(_main, "parse_args", lambda _argv: argparse.Namespace(command=_COMMAND))
    monkeypatch.setattr(_main, "SYNC_COMMANDS", {_COMMAND: _leaky_command})
    yield
    logger.remove()
    logger.add(sys.stderr)


@allure.epic("Benchmarks")
@allure.feature("Log scrubbing")
@allure.story("Traceback secret safety")
@allure.title("The benchmark CLI logs the exception without the secret frame-local")
def test_cli_traceback_hides_secret_local(leaky_cli: None, capsys: pytest.CaptureFixture[str]) -> None:
    assert _main.main([]) == 0
    captured = capsys.readouterr().err
    assert "boom" in captured
    assert _SECRET not in captured
