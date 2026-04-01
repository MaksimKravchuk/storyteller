"""Async SQLAlchemy engine and session factory."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine as _create_engine,
)


def create_async_engine(database_url: str):
    """Create an async SQLAlchemy engine."""
    return _create_engine(database_url, echo=False)


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
