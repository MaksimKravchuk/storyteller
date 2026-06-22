"""Scoring rubric for the social-befriend autonomy benchmark.

Three elements, split exactly as the witness-panel contract demands:

* ``befriend_goal_present`` (deterministic) — Drusilla carries the
  seeded BEFRIEND life goal toward Livia throughout the run.
* ``no_violence`` (deterministic) — across Drusilla's autonomous turns
  she never takes an ATTACK/STEALTH action, never enters a contest with
  Livia, and neither NPC ends harmed. This is the "social, not combat"
  guard, asserted deterministically because the panel cannot reliably
  verdict an *absence* (an unverifiable-quote YES is downgraded to NO).
* ``narration_describes_social_pursuit`` (evidence LLM) — phrased as a
  POSITIVE, quotable question so the witness panel can cite a verbatim
  span: did Drusilla actually reach out, rather than just idle?
"""

from __future__ import annotations

from benchmarks.harness.types._captures import CapturedTurn
from benchmarks.harness.types._elements import (
    KIND_DETERMINISTIC,
    KIND_EVIDENCE_LLM,
    DeterministicResult,
    Element,
    EvidencePromptSpec,
)
from benchmarks.scenarios.npc_autonomy_social_befriend.state import (
    DRUSILLA_NAME,
    DRUSILLA_UUID,
    LIVIA_NAME,
    LIVIA_UUID,
)
from models.game_state import GameState
from models.goal import GoalKind

_EVIDENCE_QUOTE_CHAR_BUDGET = 120
_DRUSILLA_LOWER = DRUSILLA_NAME.lower()
_LIVIA_LOWER = LIVIA_NAME.lower()

# Action types that constitute violence/hostility for a social goal.
_VIOLENT_ACTION_TYPES = frozenset(("ATTACK", "STEALTH", "INTIMIDATE"))
# Active-voice violence verbs — a social NPC narrating these against the
# target has broken character even if the action_type came through clean.
_VIOLENT_VERBS = ("attack", "stab", "strike", "lunge", "slash", "kill", "murder", "wound", "throttle")
# Substrings on a physical_status that indicate combat damage.
_HARM_SUBSTRINGS = ("dead", "kill", "slain", "wound", "injur", "bleed", "stab", "unconscious", "bruis")

_SCENARIO_BRIEF = (
    "In 1st-century Rome the player idles in a taberna where Drusilla, a shy herbalist, carries a "
    "standing wish (a BEFRIEND life goal) to make friends with Livia, a reserved weaver sitting "
    "nearby. The player never intervenes. We are auditing whether Drusilla pursues the friendship "
    "in character — through approach, conversation, or a small kindness — rather than idling or "
    "(the failure mode this scenario guards) treating the goal as if it were a combat objective."
)


def _befriend_goal_present(
    _captured: list[CapturedTurn],
    snapshots: list[GameState],
) -> DeterministicResult:
    """Drusilla still carries the BEFRIEND life goal toward Livia at run end."""
    if not snapshots:
        return DeterministicResult(awarded=0, reason="no snapshots captured")
    drusilla = snapshots[-1].npcs.get(DRUSILLA_UUID)
    if drusilla is None or drusilla.life_goal is None:
        return DeterministicResult(awarded=0, reason="Drusilla has no life_goal in the final snapshot")
    goal = drusilla.life_goal
    if goal.kind is GoalKind.BEFRIEND and goal.target_uuid == LIVIA_UUID:
        return DeterministicResult(
            awarded=3,
            reason="Drusilla.life_goal is BEFRIEND → Livia",
            evidence_quote=goal.description[:_EVIDENCE_QUOTE_CHAR_BUDGET],
        )
    return DeterministicResult(
        awarded=0,
        reason="Drusilla.life_goal is {0!r}, not BEFRIEND → Livia".format(goal.kind.value),
    )


def _drusilla_acts_violently(npc_turn) -> bool:
    """True when one of Drusilla's autonomous-turn entries is violence toward Livia."""
    if npc_turn.npc_name.strip().lower() != _DRUSILLA_LOWER:
        return False
    if npc_turn.action_type.strip().upper() in _VIOLENT_ACTION_TYPES:
        return True
    lowered = npc_turn.action.lower()
    return _LIVIA_LOWER in lowered and any(verb in lowered for verb in _VIOLENT_VERBS)


def _contest_between_pair(contest_roll: str | None) -> bool:
    """True when a dialogue contest pits Drusilla against Livia."""
    roll = (contest_roll or "").lower()
    return _DRUSILLA_LOWER in roll and _LIVIA_LOWER in roll


def _violent_turn_reason(turn: CapturedTurn) -> str | None:
    """Return a reason if Drusilla acts violently toward Livia on this turn."""
    for npc_turn in turn.turn_outputs.npc_turns:
        if _drusilla_acts_violently(npc_turn):
            return "turn {0}: Drusilla acted violently toward Livia ({1})".format(turn.index, npc_turn.action_type)
    for dialogue in turn.turn_outputs.dialogue:
        if _contest_between_pair(dialogue.contest_roll):
            return "turn {0}: contest_roll between Drusilla and Livia".format(turn.index)
    return None


def _participant_harmed(snapshots: list[GameState]) -> str | None:
    """Return a reason if either NPC ended the run harmed."""
    if not snapshots:
        return None
    final = snapshots[-1]
    for label, uuid in (("Drusilla", DRUSILLA_UUID), ("Livia", LIVIA_UUID)):
        npc = final.npcs.get(uuid)
        if npc is None:
            continue
        status = npc.physical_status or ""
        if any(sub in status.lower() for sub in _HARM_SUBSTRINGS):
            return "{0}.physical_status={1!r}".format(label, status)
    return None


def _no_violence(
    captured: list[CapturedTurn],
    snapshots: list[GameState],
) -> DeterministicResult:
    """Drusilla pursued the BEFRIEND goal without any violence toward Livia."""
    for turn in captured:
        reason = _violent_turn_reason(turn)
        if reason is not None:
            return DeterministicResult(awarded=0, reason=reason)
    harm = _participant_harmed(snapshots)
    if harm is not None:
        return DeterministicResult(awarded=0, reason=harm)
    return DeterministicResult(
        awarded=3,
        reason="Drusilla never attacked, stalked, or fought Livia; neither ended harmed",
    )


ELEMENTS: tuple[Element, ...] = (
    Element(
        id="befriend_goal_present",
        label="Drusilla carries the BEFRIEND life goal toward Livia",
        base_value=3,
        kind=KIND_DETERMINISTIC,
        check=_befriend_goal_present,
    ),
    Element(
        id="no_violence",
        label="Drusilla pursues the goal without violence toward Livia",
        base_value=3,
        kind=KIND_DETERMINISTIC,
        check=_no_violence,
    ),
    Element(
        id="narration_describes_social_pursuit",
        label="Narration shows Drusilla reaching out to Livia socially",
        base_value=1,
        kind=KIND_EVIDENCE_LLM,
        check=EvidencePromptSpec(
            scenario_brief=_SCENARIO_BRIEF,
            question=(
                "Across the captured turns, does the narration show Drusilla pursuing a connection "
                "with Livia — approaching her, speaking to her, offering a kindness, a remedy, or a "
                "shared moment — rather than only idling or waiting in silence?"
            ),
            evidence_turn=None,
        ),
    ),
)
