"""Best-effort in-process quota locks for beta web actions."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

_locks: dict[str, asyncio.Lock] = {}


@asynccontextmanager
async def player_lock(player_id: str) -> AsyncIterator[None]:
    """Serialize quota checks and spend-producing work per beta player.

    This prevents local concurrent requests from passing quota checks together
    before either request has persisted its active game or turn usage.
    """
    lock = _locks.setdefault(player_id, asyncio.Lock())
    async with lock:
        yield
