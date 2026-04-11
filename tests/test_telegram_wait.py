"""Tests for /wait Telegram command registration."""

from __future__ import annotations

import allure
import pytest


@allure.epic("Player Interfaces")
@allure.feature("Telegram bot")
class TestWaitCommandRegistered:
    @allure.story("Wait command registration")
    @allure.title("The cmd_wait handler is importable as a callable from interfaces.telegram_commands")
    def test_cmd_wait_importable(self):
        """cmd_wait is defined in telegram_commands module."""
        pytest.importorskip("telegram")
        from interfaces.telegram_commands import cmd_wait

        assert callable(cmd_wait)

    @allure.story("Wait command registration")
    @allure.title("The Telegram bot builder wires a /wait command handler into the application")
    def test_wait_handler_in_build_bot(self):
        """build_bot registers a /wait command handler."""
        pytest.importorskip("telegram")
        import inspect

        from interfaces.telegram_bot import build_bot

        source = inspect.getsource(build_bot)
        assert "wait" in source
