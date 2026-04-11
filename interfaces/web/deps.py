"""FastAPI dependencies for the web interface.

Tests override ``get_repo`` (and sometimes ``get_cfg``) via
``app.dependency_overrides`` so they never hit a real database.
"""

from __future__ import annotations

import importlib
import os
import typing
import uuid as _uuid
from functools import lru_cache

from fastapi import Request
from starlette.responses import Response

from config import Config, load_config

COOKIE_NAME = "web_player_id"
_STATE_PLAYER_ID = "web_player_id"
_STATE_PLAYER_MINTED = "web_player_id_minted"

_SECONDS_PER_DAY = 60 * 60 * 24
_COOKIE_MAX_AGE_DAYS = 365
_COOKIE_MAX_AGE_SECONDS = _SECONDS_PER_DAY * _COOKIE_MAX_AGE_DAYS


@lru_cache(maxsize=1)
def get_cfg() -> Config:
    """Return the process-wide Config, loading it once."""
    return load_config()


@lru_cache(maxsize=1)
def get_session_factory() -> typing.Any:
    """Return the process-wide async session factory, creating it on first use.

    Reads ``DATABASE_URL`` from the environment (same contract as
    ``run_server.py``). The ``db.engine`` module is imported lazily via
    ``importlib`` so this module can be imported under
    ``tests/_db_stubs.py``, which replaces ``db.engine`` with a MagicMock
    shim that lacks ``create_async_engine`` etc.
    """
    db_engine = importlib.import_module("db.engine")
    database_url = os.environ["DATABASE_URL"]
    engine = db_engine.create_async_engine(database_url)
    return db_engine.create_session_factory(engine)


async def get_repo() -> typing.AsyncIterator[typing.Any]:
    """Yield a ``GameRepository`` bound to a per-request async session.

    The session commits on success and rolls back on exception via
    ``db.engine.get_db``. Imports from ``db.*`` are deferred to runtime for
    the same reason as ``get_session_factory``.
    """
    db_engine = importlib.import_module("db.engine")
    db_repo = importlib.import_module("db.repository")
    factory = get_session_factory()
    async with db_engine.get_db(factory) as session:
        yield db_repo.GameRepository(session)


def get_player_id(request: Request) -> str:
    """Return the ``web_player_id`` stashed on ``request.state`` by the middleware.

    The middleware — not this dep — owns cookie minting and the Set-Cookie
    header, so the cookie is attached to every response (including 404s).
    """
    player_id = getattr(request.state, _STATE_PLAYER_ID, None)
    if player_id is None:
        # Fallback for edge cases (e.g. direct unit tests that don't route
        # through the middleware). Production always runs the middleware.
        return str(_uuid.uuid4())
    return player_id


def _stash_player_id(request: Request) -> None:
    """Read or mint a ``web_player_id`` and stash it on ``request.state``."""
    existing = request.cookies.get(COOKIE_NAME)
    if existing:
        request.state.web_player_id = existing
        request.state.web_player_id_minted = False
    else:
        request.state.web_player_id = str(_uuid.uuid4())
        request.state.web_player_id_minted = True


def _attach_player_cookie(request: Request, response: Response) -> None:
    """Set the Set-Cookie header on the outgoing response if a new id was minted."""
    if not getattr(request.state, _STATE_PLAYER_MINTED, False):
        return
    response.set_cookie(
        key=COOKIE_NAME,
        value=request.state.web_player_id,
        max_age=_COOKIE_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
    )


async def player_id_middleware(
    request: Request,
    call_next: typing.Callable[[Request], typing.Awaitable[Response]],
) -> Response:
    """Ensure every request carries a ``web_player_id`` cookie.

    On entry: read the cookie from the request, or mint a fresh UUID if none
    is present. On exit: if we minted a new id, set the Set-Cookie header on
    the outgoing response. This runs for every response — including the
    JSONResponse produced by FastAPI for ``HTTPException`` — so browsers
    persist the id even when the first request returns 404.
    """
    _stash_player_id(request)
    response = await call_next(request)
    _attach_player_cookie(request, response)
    return response
