"""Async SQLAlchemy engine and session factory."""

from __future__ import annotations

import ssl as _ssl
from contextlib import asynccontextmanager
from typing import AsyncIterator, Tuple
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine as _create_engine,
)

_SSL_ENABLED_MODES = frozenset(
    ("prefer", "require", "verify-ca", "verify-full"),
)

_SSL_DISABLED_MODES = frozenset(("disable", "allow"))

# Managed Postgres (Fly) and its proxy silently drop idle TCP connections, and a
# request cancelled mid-query (client disconnect) can hand a broken asyncpg
# connection back to the pool. Without a liveness check the next request to draw
# that connection 500s inside ``session.execute`` — the beta-auth incident.
# ``pool_pre_ping`` validates a connection before use; ``pool_recycle`` retires
# old ones proactively so they never go stale in the first place.
_POOL_RECYCLE_SECONDS = 1800


def _strip_sslmode(url_string: str) -> Tuple[str, str | None]:
    """Remove ``sslmode`` from a database URL query string."""
    parsed = urlparse(url_string)
    query_params = parse_qs(parsed.query)
    sslmode = query_params.pop("sslmode", [None])[0]
    return urlunparse(
        parsed._replace(
            query=urlencode({key: entry[0] for key, entry in query_params.items()}),
        )
    ), sslmode


def _adapt_url_for_asyncpg(database_url: str) -> Tuple[str, dict]:
    """Strip ``sslmode`` query param and return ``(clean_url, connect_args)``.

    asyncpg does not accept the libpq ``sslmode`` query parameter — it uses
    the ``ssl`` keyword instead.  This converts URLs produced by managed
    Postgres providers (Fly, Supabase, etc.) so they work with asyncpg.
    """
    clean_url, sslmode = _strip_sslmode(database_url)
    if urlparse(clean_url).scheme in ("postgres", "postgresql"):
        clean_url = urlunparse(urlparse(clean_url)._replace(scheme="postgresql+asyncpg"))
    connect_args: dict = {}
    if sslmode in _SSL_ENABLED_MODES:
        connect_args["ssl"] = _ssl.create_default_context()
    elif sslmode in _SSL_DISABLED_MODES:
        connect_args["ssl"] = False
    return clean_url, connect_args


def create_async_engine(database_url: str):
    """Create an async SQLAlchemy engine with pooled-connection liveness checks."""
    url, connect_args = _adapt_url_for_asyncpg(database_url)
    return _create_engine(
        url,
        echo=False,
        connect_args=connect_args,
        pool_pre_ping=True,
        pool_recycle=_POOL_RECYCLE_SECONDS,
    )


def create_session_factory(engine) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory bound to the given engine."""
    return async_sessionmaker(engine, expire_on_commit=False)


@asynccontextmanager
async def get_db(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Yield an async DB session, committing on success or rolling back on error."""
    async with session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            await session.commit()
