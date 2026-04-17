"""Shared Actor-related test helpers — mock builders that return :class:`ActorReply`."""

from __future__ import annotations

from unittest.mock import AsyncMock

from cast.schemas.actor_reply import ActorReply


def actor_reply(text: str = "", revealed_names: list[str] | None = None) -> ActorReply:
    """Build an :class:`ActorReply` for tests."""
    return ActorReply(text=text, revealed_names=list(revealed_names or []))


def make_mock_actor(text: str = "", revealed_names: list[str] | None = None) -> AsyncMock:
    """Create an Actor-shaped mock whose ``execute``/``act`` return an :class:`ActorReply`."""
    reply = actor_reply(text=text, revealed_names=revealed_names)
    mock = AsyncMock()
    mock.act = AsyncMock(return_value=reply)
    mock.execute = AsyncMock(return_value=reply)
    return mock
