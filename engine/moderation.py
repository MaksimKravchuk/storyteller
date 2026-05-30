"""Engine-side glue for the content-safety pipeline.

Wraps the moderator's inbound/outbound checks so :class:`GameEngine`
stays focused on game flow. Both helpers tolerate a ``None`` moderator
(safety disabled by config) and raise :class:`SafetyRejectedError`
on inbound rejection so HTTP and chat surfaces can translate it.
"""

from __future__ import annotations

from safety.moderator import Moderator, SafetyRejectedError
from safety.result import ModerationDirection


async def moderate_input(moderator: Moderator | None, player_action: str) -> None:
    """Run inbound moderation; raise :class:`SafetyRejectedError` on a hit."""
    if moderator is None:
        return
    moderation = await moderator.check(player_action, direction=ModerationDirection.INPUT)
    if moderation.flagged:
        raise SafetyRejectedError(moderator.refusal_message(moderation), moderation)


async def moderate_output(moderator: Moderator | None, narration: str) -> str:
    """Run outbound moderation; substitute a safe fallback on a hit."""
    if moderator is None:
        return narration
    moderation = await moderator.check(narration, direction=ModerationDirection.OUTPUT)
    if moderation.flagged:
        return moderator.fallback_narration(moderation)
    return narration
