"""WAIT-turn rendering helpers for the Narrator (KER-20).

Lives in its own module rather than inside :mod:`cast.narrator` so
``cast/narrator.py`` stays under the project-wide WPS202 module-member
budget alongside the prior-damage helpers from KER-16 and the original
Narrator helpers. No ``self`` state is needed; every function takes the
inputs it renders from.

Re-exports:

* :func:`format_wait_context_bullets` — renders a :class:`WaitContext`
  as a list of bullet lines for the narrator prompt kwargs.
* :func:`append_wait_parts` — appends WAIT raw-material lines onto an
  existing ``raw_parts`` list. Falls back to the original stub wait
  line when ``input_data.wait_context`` is ``None`` so forced-wait
  turns (and any historical call sites that never populate a
  :class:`WaitContext`) keep their pre-KER-20 output.
"""

from __future__ import annotations

from cast.schemas.turn_outputs import TurnOutputs, WaitContext


def format_wait_line(wait_reason: str | None) -> str:
    """Render a single raw-parts line describing the player's wait state.

    Historically lived inside :mod:`cast.narrator`; moved here in
    KER-20 so ``narrator.py`` stays within its WPS202 budget.
    """
    if (wait_reason or "") in ("", "voluntary"):
        return "The player waits and observes the surroundings."
    return "The player cannot act — they are {0}.".format(wait_reason)


def format_wait_context_bullets(ctx: WaitContext) -> list[str]:
    """Render a :class:`WaitContext` as bullet lines for the narrator prompt."""
    bullets: list[str] = []
    for thread in ctx.active_threads:
        bullets.append("- thread: {0}".format(thread.description))
    for label in ctx.on_shift_npcs:
        bullets.append("- on shift: {0}".format(label))
    for event_line in ctx.imminent_events:
        bullets.append("- stirring: {0}".format(event_line))
    return bullets


def append_wait_parts(raw_parts: list[str], input_data: TurnOutputs) -> None:
    """Render the rich wait-context material when present, else the stub line.

    When :class:`cast.director_execution.PlanExecutor` attaches a
    :class:`WaitContext` (KER-20) the Narrator surfaces active
    threads, on-shift NPCs and imminent events so the raw material
    never bottoms out at ``"No specific scene data."``. When the
    field is ``None`` (forced-wait fallback, pre-chronicler turns)
    we keep the original stub so existing tests still pass.
    """
    ctx = input_data.wait_context
    if ctx is None:
        raw_parts.append(format_wait_line(input_data.wait_reason))
        return
    raw_parts.append("The player waits for roughly {0:.1f} hours.".format(ctx.hours_waited))
    for thread in ctx.active_threads:
        raw_parts.append("Ongoing thread: {0}".format(thread.description))
    for label in ctx.on_shift_npcs:
        raw_parts.append("On shift nearby: {0}".format(label))
    for event_line in ctx.imminent_events:
        raw_parts.append("Stirring in the background: {0}".format(event_line))
