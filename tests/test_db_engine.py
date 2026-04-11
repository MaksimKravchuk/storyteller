"""Tests for db.engine URL adaptation and engine creation.

conftest.py loads _db_stubs which replaces db.engine in sys.modules with a
mock.  We force-load the real module once at import time, before the stub
takes effect for subsequent test modules.
"""

from __future__ import annotations

import os
import ssl
import sys

import allure

# Force the real db.engine into sys.modules before _db_stubs can stub it.
_stashed_stub = sys.modules.pop("db.engine", None)
sys.modules.pop("db", None)

from db import engine as _real_engine  # noqa: E402, WPS433

# Restore stub so other test modules are not affected.
if _stashed_stub is not None:
    sys.modules["db.engine"] = _stashed_stub

_SSL_KEY = "ssl"


@allure.epic("Memory & Persistence")
@allure.feature("Database engine")
class TestStripSslmode:
    @allure.story("URL sslmode strip")
    @allure.title("_strip_sslmode removes the sslmode query parameter and returns the extracted mode")
    def test_removes_sslmode_param(self):
        url = "postgresql://u:p@host:5432/db?sslmode=require"
        clean, mode = _real_engine._strip_sslmode(url)
        assert "sslmode" not in clean
        assert mode == "require"

    @allure.story("URL sslmode strip")
    @allure.title("_strip_sslmode leaves other query parameters like connect_timeout untouched")
    def test_preserves_other_params(self):
        url = "postgresql://u:p@host/db?sslmode=require&connect_timeout=10"
        clean, mode = _real_engine._strip_sslmode(url)
        assert "connect_timeout=10" in clean
        assert "sslmode" not in clean
        assert mode == "require"

    @allure.story("URL sslmode strip")
    @allure.title("_strip_sslmode returns the original URL unchanged and None mode when no sslmode is present")
    def test_no_sslmode_returns_none(self):
        url = "postgresql://u:p@host/db"
        clean, mode = _real_engine._strip_sslmode(url)
        assert clean == url
        assert mode is None


@allure.epic("Memory & Persistence")
@allure.feature("Database engine")
class TestAdaptUrlForAsyncpg:
    @allure.story("Engine creation")
    @allure.title("sslmode=require yields an SSLContext in the asyncpg connect args")
    def test_require_produces_ssl_context(self):
        url = "postgresql://u:p@host/db?sslmode=require"
        clean, args = _real_engine._adapt_url_for_asyncpg(url)
        assert "sslmode" not in clean
        assert isinstance(args[_SSL_KEY], ssl.SSLContext)

    @allure.story("Engine creation")
    @allure.title("sslmode=prefer yields an SSLContext in the asyncpg connect args")
    def test_prefer_produces_ssl_context(self):
        url = "postgresql://u:p@host/db?sslmode=prefer"
        _, args = _real_engine._adapt_url_for_asyncpg(url)
        assert isinstance(args[_SSL_KEY], ssl.SSLContext)

    @allure.story("Engine creation")
    @allure.title("sslmode=disable explicitly sets ssl=False so asyncpg does not attempt SSL negotiation")
    def test_disable_produces_ssl_false(self):
        """sslmode=disable must explicitly pass ssl=False to asyncpg.

        Without this, asyncpg defaults to attempting SSL negotiation,
        which fails on Fly.io internal networks.
        """
        url = "postgresql://u:p@host/db?sslmode=disable"
        _, args = _real_engine._adapt_url_for_asyncpg(url)
        assert args[_SSL_KEY] is False

    @allure.story("Engine creation")
    @allure.title("A URL without sslmode produces an empty connect args dict")
    def test_no_sslmode_returns_empty_args(self):
        url = "postgresql://u:p@host/db"
        _, args = _real_engine._adapt_url_for_asyncpg(url)
        assert args == {}

    @allure.story("Engine creation")
    @allure.title("sslmode=allow is treated like disable and passes ssl=False to asyncpg")
    def test_allow_produces_ssl_false(self):
        """sslmode=allow means prefer no SSL — treat like disable."""
        url = "postgresql://u:p@host/db?sslmode=allow"
        _, args = _real_engine._adapt_url_for_asyncpg(url)
        assert args[_SSL_KEY] is False


@allure.epic("Memory & Persistence")
@allure.feature("Database engine")
class TestAlembicEnvConnectArgs:
    """Verify that Alembic env passes connect_args to the engine."""

    @allure.story("Alembic integration")
    @allure.title(
        "alembic/env.py forwards connect_args from _adapt_url_for_asyncpg so SSL settings apply during migrations"
    )
    def test_does_not_discard(self):
        """alembic/env.py must use connect_args from _adapt_url_for_asyncpg.

        Previously it discarded them with ``db_url, _ = ...``,
        meaning SSL config was never applied during migrations.
        """
        source_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "alembic",
            "env.py",
        )
        with open(source_path) as fh:
            source = fh.read()

        assert "db_url, _ =" not in source, "alembic/env.py discards connect_args"
        assert "connect_args=" in source, "alembic/env.py must pass connect_args to the async engine"
