"""Engine-side glue for the content-safety pipeline.

Wraps the moderator's inbound/outbound checks so :class:`GameEngine`
stays focused on game flow. Both helpers tolerate a ``None`` moderator
(safety disabled by config) and raise :class:`SafetyRejectedError`
on inbound rejection so HTTP and chat surfaces can translate it.
"""

from __future__ import annotations

import re
from typing import Awaitable, Callable

from llm import turn_stream
from safety.moderator import Moderator, SafetyRejectedError
from safety.result import ModerationDirection, ModerationResult

# A sentence ends at terminal punctuation (plus closing quotes/brackets) followed by whitespace, or at a line break.
_SENTENCE_END = re.compile(r"[.!?…][\"'»”)\]]*\s+|\n+")


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


class SentenceGate:
    """Stream sink that releases Narrator prose only after outbound moderation passes.

    Text is buffered to sentence boundaries and each completed chunk is
    checked before it reaches the player. After the first hit nothing more
    is released and :attr:`blocked` holds the result, so the engine can
    replace the whole passage. With safety disabled, deltas pass straight
    through.
    """

    def __init__(self, moderator: Moderator | None, sink: turn_stream.TurnStreamSink) -> None:
        self._moderator = moderator
        self._sink = sink
        self._pending = ""
        self.blocked: ModerationResult | None = None

    async def stage(self, name: str) -> None:
        """Forward a stage change unchanged."""
        await self._sink.stage(name)

    async def delta(self, text: str) -> None:
        """Buffer ``text`` and release every sentence it completes."""
        if self._moderator is None:
            await self._sink.delta(text)
            return
        self._pending += text
        boundaries = [match.end() for match in _SENTENCE_END.finditer(self._pending)]
        if boundaries:
            ready = self._pending[: boundaries[-1]]
            self._pending = self._pending[boundaries[-1] :]
            await self._release(ready)

    async def flush(self) -> None:
        """Release the unterminated tail once the Narrator has finished."""
        ready = self._pending
        self._pending = ""
        await self._release(ready)

    async def _release(self, text: str) -> None:
        # shortcut: moderation runs inline, so the stream waits on each check; pipeline it if pauses show.
        if self._moderator is None or self.blocked is not None or not text:
            return
        moderation = await self._moderator.check(text, direction=ModerationDirection.OUTPUT)
        if moderation.flagged:
            self.blocked = moderation
            return
        await self._sink.delta(text)


async def moderate_narration(moderator: Moderator | None, narrate: Callable[[], Awaitable[str]]) -> str:
    """Run ``narrate`` and return its moderated prose.

    When a turn stream is bound, prose reaches it sentence-by-sentence
    through a :class:`SentenceGate`; a hit there replaces the whole passage.
    The full text still gets the regular outbound check, since a passage can
    read worse than any single sentence of it.
    """
    sink = turn_stream.current_sink()
    if sink is None:
        return await moderate_output(moderator, await narrate())
    gate = SentenceGate(moderator, sink)
    with turn_stream.bound(gate):
        narration = await narrate()
    await gate.flush()
    if gate.blocked is not None and moderator is not None:
        return moderator.fallback_narration(gate.blocked)
    return await moderate_output(moderator, narration)
