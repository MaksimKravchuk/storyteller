"""WAIT-turn rendering helpers for the Narrator (KER-20).

Lives in its own module rather than inside :mod:`cast.narrator` so
``cast/narrator.py`` stays under the project-wide WPS202 module-member
budget alongside the prior-damage helpers from KER-16 and the original
Narrator helpers. No ``self`` state is needed; every function takes the
inputs it renders from.

Re-exports:

* :func:`format_wait_context_bullets` — renders a :class:`WaitContext`
  as a list of localised bullet lines for the narrator prompt kwargs.
* :func:`append_wait_parts` — appends localised WAIT raw-material lines
  onto an existing ``raw_parts`` list. Falls back to the stub wait
  line when ``input_data.wait_context`` is ``None`` so forced-wait
  turns (and any historical call sites that never populate a
  :class:`WaitContext`) keep their pre-KER-20 output shape.
"""

from __future__ import annotations

from cast.narrator_labels import NarratorLabels
from cast.schemas.turn_outputs import TurnOutputs, WaitContext


def format_wait_line(wait_reason: str | None, labels: NarratorLabels) -> str:
    """Render a single raw-parts line describing the player's wait state.

    Historically lived inside :mod:`cast.narrator`; moved here in
    KER-20 so ``narrator.py`` stays within its WPS202 budget. The
    *labels* parameter carries the locale-appropriate phrasings.
    """
    if (wait_reason or "") in ("", "voluntary"):
        return labels.waits_and_observes
    return labels.cannot_act.format(wait_reason)


def format_wait_context_bullets(ctx: WaitContext, labels: NarratorLabels) -> list[str]:
    """Render a :class:`WaitContext` as localised bullet lines."""
    bullets: list[str] = []
    for thread in ctx.active_threads:
        bullets.append(labels.wait_bullet_thread.format(thread.description))
    for npc_label in ctx.on_shift_npcs:
        bullets.append(labels.wait_bullet_on_shift.format(npc_label))
    for event_line in ctx.imminent_events:
        bullets.append(labels.wait_bullet_stirring.format(event_line))
    return bullets


def append_wait_parts(raw_parts: list[str], input_data: TurnOutputs, labels: NarratorLabels) -> None:
    """Render the rich wait-context material when present, else the stub line.

    When :class:`cast.director_execution.PlanExecutor` attaches a
    :class:`WaitContext` (KER-20) the Narrator surfaces active
    threads, on-shift NPCs and imminent events so the raw material
    never bottoms out at the "no data" placeholder. When the field is
    ``None`` (forced-wait fallback, pre-chronicler turns) we keep the
    stub-line shape so existing tests still pass.
    """
    ctx = input_data.wait_context
    if ctx is None:
        raw_parts.append(format_wait_line(input_data.wait_reason, labels))
        return
    raw_parts.append(labels.waits_for_hours.format(ctx.hours_waited))
    for thread in ctx.active_threads:
        raw_parts.append(labels.ongoing_thread.format(thread.description))
    for npc_label in ctx.on_shift_npcs:
        raw_parts.append(labels.on_shift_nearby.format(npc_label))
    for event_line in ctx.imminent_events:
        raw_parts.append(labels.stirring_background.format(event_line))
