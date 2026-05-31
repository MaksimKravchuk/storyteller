"""Scrub secrets from log messages before they hit any sink.

Exposes a loguru patcher so every log record emitted by the application and
tests is run through a redaction pass.
The guarantee is pipeline-level: any sink (stderr, file, network)
downstream of the patcher receives already-scrubbed messages.

Call :func:`install_scrubber` once at process start (``run_server.py`` or
test conftest). It is idempotent — calling it again replaces
the patcher reference with the same function, which is a no-op.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterable
from typing import Any

from loguru import logger

REDACTED = "***REDACTED***"

# loguru renders each frame's local VALUES into the formatted traceback when
# ``diagnose`` is enabled — a sink-time path the patcher below never sees, so a
# frame holding ``Config(openai_api_key=...)`` leaks the key into logs despite
# scrub_log_record. Production handlers must keep diagnose disabled. (``backtrace``
# renders no values and stays at loguru's default — not a leak vector, still
# useful for debugging.)
LOGURU_DIAGNOSE_ENABLED = False

_PatternRule = tuple[re.Pattern[str], str]

# Order matters: specific patterns first, otherwise the generic ``sk-...``
# rule would swallow the ``sk-ant-...`` / ``sk-proj-...`` prefixes and the
# redacted output would lose the useful provider hint.
_PATTERNS: tuple[_PatternRule, ...] = (
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}"), "sk-ant-{0}".format(REDACTED)),
    (re.compile(r"sk-proj-[A-Za-z0-9_\-]{20,}"), "sk-proj-{0}".format(REDACTED)),
    (re.compile(r"sk-[A-Za-z0-9_\-]{20,}"), "sk-{0}".format(REDACTED)),
    (
        re.compile(r"(?i)authorization:\s*bearer\s+\S+"),
        "Authorization: Bearer {0}".format(REDACTED),
    ),
    (
        re.compile(r"(?i)bearer\s+[A-Za-z0-9_\-.]{20,}"),
        "Bearer {0}".format(REDACTED),
    ),
    (
        re.compile(r"postgres(?:ql)?://[^:\s]+:[^@\s]+@"),
        "postgres://{0}@".format(REDACTED),
    ),
)

_SECRET_ENV_VARS: tuple[str, ...] = (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GITHUB_TOKEN",
    "FLY_API_TOKEN",
    "DATABASE_URL",
)

_MIN_SECRET_LENGTH = 8


def _env_secret_values() -> tuple[str, ...]:
    """Return current non-empty, sufficiently-long secret env var values."""
    collected: list[str] = []
    for name in _SECRET_ENV_VARS:
        value_raw = os.environ.get(name)
        if value_raw and len(value_raw) >= _MIN_SECRET_LENGTH:
            collected.append(value_raw)
    return tuple(collected)


def _apply_regex_patterns(text: str) -> str:
    scrubbed = text
    for pattern, replacement in _PATTERNS:
        scrubbed = pattern.sub(replacement, scrubbed)
    return scrubbed


def _apply_literal_replacements(text: str, literals: Iterable[str]) -> str:
    # Longest first so a shorter prefix can't shadow a longer secret value.
    ordered = sorted(
        {literal for literal in literals if literal and len(literal) >= _MIN_SECRET_LENGTH},
        key=len,
        reverse=True,
    )
    scrubbed = text
    for secret in ordered:
        scrubbed = scrubbed.replace(secret, REDACTED)
    return scrubbed


def scrub_secrets(text: str, *, extra_values: Iterable[str] = ()) -> str:
    """Redact API keys, bearer tokens, and DB URLs from ``text``.

    Applies the regex table in priority order, then a literal replacement
    pass for values combined from ``extra_values`` and the current
    process' secret environment variables. Literals shorter than
    :data:`_MIN_SECRET_LENGTH` are ignored to avoid redacting common
    substrings.
    """
    if not text:
        return text
    after_regex = _apply_regex_patterns(text)
    combined_literals: tuple[str, ...] = (*_env_secret_values(), *tuple(extra_values))
    return _apply_literal_replacements(after_regex, combined_literals)


def scrub_log_record(record: Any) -> None:
    """Loguru patcher: sanitize ``message`` and string ``extra`` fields in place.

    Typed as :data:`Any` because loguru's ``patcher`` slot is declared
    against its internal ``Record`` TypedDict which is not part of the
    public API. Accepting ``Any`` keeps the function compatible with
    :meth:`loguru.Logger.configure` without a type-ignore suppression.
    """
    if not isinstance(record, dict):
        return
    message = record.get("message")
    if isinstance(message, str):
        record["message"] = scrub_secrets(message)
    extra = record.get("extra")
    if isinstance(extra, dict):
        _scrub_extra_in_place(extra)


def _scrub_extra_in_place(extra: dict[str, Any]) -> None:
    for key, raw_value in tuple(extra.items()):
        if isinstance(raw_value, str):
            extra[key] = scrub_secrets(raw_value)


def install_scrubber() -> None:
    """Install the scrubbing patcher on the global loguru logger.

    Idempotent — loguru replaces the patcher reference with the same
    function on repeat calls, which is a no-op. Other existing
    configuration (handlers, extra, levels) is left untouched because
    ``logger.configure`` only modifies parameters that are passed.
    """
    logger.configure(patcher=scrub_log_record)
