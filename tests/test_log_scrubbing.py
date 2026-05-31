"""Tests for the log-scrubbing patcher used across production and tests."""

from __future__ import annotations

import io

import allure
import pytest
from loguru import logger

from log_scrubbing import (
    LOGURU_DIAGNOSE_ENABLED,
    REDACTED,
    install_scrubber,
    scrub_log_record,
    scrub_secrets,
)


def _raise_with_secret_local(api_key: str) -> None:
    """Raise with ``api_key`` bound as a frame local.

    loguru's ``diagnose=True`` renders every frame's local values into the
    formatted traceback, so this is exactly the shape that leaked
    ``Config(openai_api_key=...)`` into production logs.
    """
    raise ValueError("boom")


class _ConfigureSpy:
    """Record the kwargs of every ``loguru.logger.configure`` call."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def __call__(self, **kwargs: object) -> None:
        self.calls.append(dict(kwargs))


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Log scrubbing")
class TestScrubSecretsPatterns:
    @allure.story("OpenAI key patterns")
    @allure.title("scrub_secrets replaces an ``sk-`` OpenAI-style API key inline")
    def test_openai_key_pattern(self) -> None:
        text = "Authorization failed with key=sk-abcdefghijklmnopqrstuv trailing"
        result = scrub_secrets(text)
        assert "sk-abcdefghijklmnopqrstuv" not in result
        assert "sk-***REDACTED***" in result
        assert "trailing" in result

    @allure.story("OpenAI key patterns")
    @allure.title("scrub_secrets replaces an ``sk-proj-`` OpenAI project key inline")
    def test_openai_project_key_pattern(self) -> None:
        text = "token sk-proj-ABCDEFGHIJKLMNOPQRSTUVWX here"
        result = scrub_secrets(text)
        assert "sk-proj-ABCDEFGHIJKLMNOPQRSTUVWX" not in result
        assert "sk-proj-***REDACTED***" in result

    @allure.story("Anthropic key patterns")
    @allure.title("scrub_secrets replaces an ``sk-ant-`` Anthropic key and keeps the provider hint")
    def test_anthropic_key_pattern(self) -> None:
        text = "leaked sk-ant-api01ABCDEFGHIJKLMNOPQ oops"
        result = scrub_secrets(text)
        assert "sk-ant-api01ABCDEFGHIJKLMNOPQ" not in result
        assert "sk-ant-***REDACTED***" in result
        assert "sk-***REDACTED***" not in result

    @allure.story("Anthropic key patterns")
    @allure.title("scrub_secrets short key that does not meet length threshold is left alone")
    def test_short_key_not_matched(self) -> None:
        text = "not-a-key sk-short rest"
        assert scrub_secrets(text) == text

    @allure.story("Authorization header")
    @allure.title("scrub_secrets redacts a full ``Authorization: Bearer ...`` header line")
    def test_authorization_header(self) -> None:
        text = "GET /v1 Authorization: Bearer abc1234567890xyz9876 end"
        result = scrub_secrets(text)
        assert "abc1234567890xyz9876" not in result
        assert "Authorization: Bearer ***REDACTED***" in result

    @allure.story("Authorization header")
    @allure.title("scrub_secrets redacts a naked ``Bearer <token>`` reference")
    def test_bearer_inline(self) -> None:
        text = "sent bearer abc1234567890xyz9876foo now"
        result = scrub_secrets(text)
        assert "abc1234567890xyz9876foo" not in result
        assert "Bearer ***REDACTED***" in result

    @allure.story("Database URL")
    @allure.title("scrub_secrets strips the userinfo from a postgres DSN leaving host and path")
    def test_postgres_dsn(self) -> None:
        text = "connect postgres://admin:supersecret@db.internal:5432/app now"
        result = scrub_secrets(text)
        assert "supersecret" not in result
        assert "postgres://***REDACTED***@db.internal:5432/app" in result

    @allure.story("No-op path")
    @allure.title("scrub_secrets returns the input unchanged when no secrets are present")
    def test_noop(self) -> None:
        text = "agent=Director duration_ms=42 prompt_tokens=100"
        assert scrub_secrets(text) == text

    @allure.story("No-op path")
    @allure.title("scrub_secrets returns an empty string unchanged without raising")
    def test_empty_input(self) -> None:
        assert scrub_secrets("") == ""


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Log scrubbing")
class TestScrubSecretsEnvValues:
    @allure.story("Environment replacement")
    @allure.title("scrub_secrets replaces literal OPENAI_API_KEY value from the current environment")
    def test_env_var_literal_replaced(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "my-very-own-secret-value-12345")
        text = "calling api with key my-very-own-secret-value-12345 and more"
        result = scrub_secrets(text)
        assert "my-very-own-secret-value-12345" not in result
        assert REDACTED in result

    @allure.story("Environment replacement")
    @allure.title("scrub_secrets ignores env values shorter than the minimum secret length threshold")
    def test_short_env_value_ignored(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GITHUB_TOKEN", "short")
        text = "some short literal in output"
        assert scrub_secrets(text) == text

    @allure.story("Environment replacement")
    @allure.title("scrub_secrets accepts caller-supplied extra_values and redacts them alongside env values")
    def test_extra_values_redacted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        text = "leaking custom-secret-value-1234 in the middle"
        result = scrub_secrets(text, extra_values=("custom-secret-value-1234",))
        assert "custom-secret-value-1234" not in result
        assert REDACTED in result


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Log scrubbing")
class TestScrubLogRecord:
    @allure.story("Loguru patcher")
    @allure.title("scrub_log_record rewrites ``record['message']`` in place when it contains a secret")
    def test_mutates_message(self) -> None:
        record: dict = {
            "message": "key sk-abcdefghijklmnopqrstuv tail",
            "extra": {},
        }
        scrub_log_record(record)
        assert "sk-abcdefghijklmnopqrstuv" not in record["message"]
        assert "sk-***REDACTED***" in record["message"]

    @allure.story("Loguru patcher")
    @allure.title("scrub_log_record sanitizes string values inside ``record['extra']``")
    def test_mutates_string_extras(self) -> None:
        record: dict = {
            "message": "clean message",
            "extra": {"payload": "sk-ant-api01ABCDEFGHIJKLMNOPQ"},
        }
        scrub_log_record(record)
        assert "sk-ant-api01ABCDEFGHIJKLMNOPQ" not in record["extra"]["payload"]
        assert "sk-ant-***REDACTED***" in record["extra"]["payload"]

    @allure.story("Loguru patcher")
    @allure.title("scrub_log_record leaves non-string extras untouched")
    def test_leaves_numeric_extras_alone(self) -> None:
        record: dict = {
            "message": "clean",
            "extra": {"duration_ms": 42, "count": 7},
        }
        scrub_log_record(record)
        assert record["extra"]["duration_ms"] == 42
        assert record["extra"]["count"] == 7

    @allure.story("Loguru patcher")
    @allure.title("scrub_log_record does not raise when ``record['message']`` is missing or wrong type")
    def test_robust_to_non_string_message(self) -> None:
        record: dict = {"message": None, "extra": {}}
        scrub_log_record(record)
        assert record["message"] is None


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Log scrubbing")
class TestInstallScrubber:
    @allure.story("Install idempotence")
    @allure.title("install_scrubber configures the patcher and is safe to call multiple times")
    def test_install_is_idempotent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        spy = _ConfigureSpy()
        monkeypatch.setattr(logger, "configure", spy)
        install_scrubber()
        install_scrubber()
        assert len(spy.calls) == 2
        for call_kwargs in spy.calls:
            assert call_kwargs == {"patcher": scrub_log_record}


@allure.epic("Engine & LLM Infrastructure")
@allure.feature("Log scrubbing")
class TestTracebackDiagnoseSecretSafety:
    """The message patcher cannot reach loguru's diagnose traceback rendering;
    production sinks must disable ``diagnose`` instead."""

    @allure.story("Traceback secret safety")
    @allure.title("Production keeps loguru diagnose disabled")
    def test_production_diagnose_is_disabled(self) -> None:
        assert LOGURU_DIAGNOSE_ENABLED is False

    @allure.story("Traceback secret safety")
    @allure.title("The production diagnose setting logs the exception but never renders the secret frame-local")
    def test_diagnose_disabled_sink_does_not_leak_secret(self) -> None:
        secret = "sk-proj-{0}".format("A" * 40)
        captured = self._capture_exception_log(secret, diagnose=LOGURU_DIAGNOSE_ENABLED)
        assert "boom" in captured
        assert secret not in captured

    @allure.story("Traceback secret safety")
    @allure.title("Control: with diagnose enabled the same secret WOULD leak, proving the guard is load-bearing")
    def test_diagnose_enabled_sink_would_leak_secret(self) -> None:
        secret = "sk-proj-{0}".format("B" * 40)
        captured = self._capture_exception_log(secret, diagnose=True)
        assert secret in captured

    def _capture_exception_log(self, secret: str, *, diagnose: bool) -> str:
        sink = io.StringIO()
        handler_id = logger.add(sink, level="DEBUG", colorize=False, backtrace=False, diagnose=diagnose)
        try:
            _raise_with_secret_local(secret)
        except ValueError:
            logger.opt(exception=True).error("request failed")
        finally:
            logger.remove(handler_id)
        return sink.getvalue()
