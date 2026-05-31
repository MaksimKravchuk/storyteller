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
import pytest

# Force the real db.engine into sys.modules before _db_stubs can stub it.
_stashed_stub = sys.modules.pop("db.engine", None)
sys.modules.pop("db", None)

from db import engine as _real_engine  # noqa: E402, WPS433

# Guard: we must be exercising the real module, not a MagicMock left over
# from tests/_db_stubs.py. If this assertion fails, conftest collection order
# has changed and the stub is winning.
assert hasattr(_real_engine, "_strip_sslmode"), (
    "test_db_engine.py must import the real db.engine module; "
    "got a stub instead — check conftest.py / _db_stubs.py ordering"
)
assert callable(_real_engine._strip_sslmode)

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
class TestEngineAndGetDb:
    @allure.story("Engine creation")
    @allure.title("create_async_engine returns a SQLAlchemy AsyncEngine for a plain postgres URL")
    def test_create_async_engine_returns_engine(self):
        engine = _real_engine.create_async_engine("postgresql+asyncpg://u:p@host/db")
        from sqlalchemy.ext.asyncio import AsyncEngine

        assert isinstance(engine, AsyncEngine)

    @allure.story("Engine creation")
    @allure.title("create_async_engine enables pool_pre_ping so broken pooled connections are replaced, not 500ed")
    def test_create_async_engine_enables_pool_pre_ping(self):
        """A pooled connection left in a broken state (managed PG idle-drop,
        an asyncpg operation interrupted by a client disconnect) must be
        detected and recycled before a request uses it — otherwise the next
        request to draw it 500s inside ``session.execute``. ``pool_pre_ping``
        is the lever that guarantees the liveness check."""
        engine = _real_engine.create_async_engine("postgresql+asyncpg://u:p@host/db")
        assert engine.pool._pre_ping is True

    @allure.story("Engine creation")
    @allure.title("create_async_engine sets a finite pool_recycle so stale connections are proactively retired")
    def test_create_async_engine_sets_pool_recycle(self):
        engine = _real_engine.create_async_engine("postgresql+asyncpg://u:p@host/db")
        assert engine.pool._recycle > 0

    @allure.story("Engine creation")
    @allure.title("create_session_factory returns a callable async_sessionmaker bound to the engine")
    def test_create_session_factory_returns_sessionmaker(self):
        from sqlalchemy.ext.asyncio import async_sessionmaker

        engine = _real_engine.create_async_engine("postgresql+asyncpg://u:p@host/db")
        factory = _real_engine.create_session_factory(engine)
        assert isinstance(factory, async_sessionmaker)

    @allure.story("Session lifecycle")
    @allure.title("get_db commits on successful exit, and commit happens before __aexit__")
    @pytest.mark.asyncio
    async def test_get_db_commits_before_aexit(self):
        from unittest.mock import AsyncMock, MagicMock

        call_order: list[str] = []
        session = AsyncMock()
        session.commit = AsyncMock(side_effect=lambda: call_order.append("commit"))
        session.rollback = AsyncMock(side_effect=lambda: call_order.append("rollback"))
        aexit = AsyncMock(side_effect=lambda *_args, **_kwargs: call_order.append("aexit") or False)

        factory = MagicMock()
        factory.return_value.__aenter__ = AsyncMock(return_value=session)
        factory.return_value.__aexit__ = aexit

        async with _real_engine.get_db(factory) as yielded:
            assert yielded is session

        # commit must happen inside get_db, BEFORE __aexit__ — a refactor that
        # moved commit into __aexit__ would show call_order == ["aexit"].
        assert call_order == ["commit", "aexit"]
        session.rollback.assert_not_awaited()

    @allure.story("Session lifecycle")
    @allure.title("get_db rolls back before __aexit__ when the caller raises inside the context")
    @pytest.mark.asyncio
    async def test_get_db_rolls_back_before_aexit(self):
        from unittest.mock import AsyncMock, MagicMock

        call_order: list[str] = []
        session = AsyncMock()
        session.commit = AsyncMock(side_effect=lambda: call_order.append("commit"))
        session.rollback = AsyncMock(side_effect=lambda: call_order.append("rollback"))
        aexit = AsyncMock(side_effect=lambda *_args, **_kwargs: call_order.append("aexit") or False)

        factory = MagicMock()
        factory.return_value.__aenter__ = AsyncMock(return_value=session)
        factory.return_value.__aexit__ = aexit

        with pytest.raises(RuntimeError, match="boom"):
            async with _real_engine.get_db(factory):
                raise RuntimeError("boom")

        assert call_order == ["rollback", "aexit"]
        session.commit.assert_not_awaited()


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
