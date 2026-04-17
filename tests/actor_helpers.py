"""Shared Actor-related test helpers.

Post-KER-29 the Actor promotes its return type from ``str`` to
:class:`cast.schemas.actor_reply.ActorReply`, so Director tests that
mocked ``actor.execute`` to return a bare string now need a helper
that wraps the text in an :class:`ActorReply`. Kept in its own module
so :mod:`tests.director_helpers` stays under its module-member budget.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

from cast.schemas.actor_reply import ActorReply


def actor_reply(text: str = "", revealed_names: list[str] | None = None) -> ActorReply:
    """Build an :class:`ActorReply` for tests.

    Kept short so mock return values stay readable in test setup.
    """
    return ActorReply(text=text, revealed_names=list(revealed_names or []))


def make_mock_actor(text: str = "", revealed_names: list[str] | None = None) -> AsyncMock:
    """Create an Actor-shaped mock whose ``execute``/``act`` return an :class:`ActorReply`.

    Post-KER-29 the Actor promotes its return type to :class:`ActorReply`,
    so Director tests that used to hand back a bare string now need
    this wrapper to stay compatible with ``director_dialogue`` and
    ``director_retaliation`` unwrapping ``reply.text``.
    """
    reply = actor_reply(text=text, revealed_names=revealed_names)
    mock = AsyncMock()
    mock.act = AsyncMock(return_value=reply)
    mock.execute = AsyncMock(return_value=reply)
    return mock
