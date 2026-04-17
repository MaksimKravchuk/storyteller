"""Proximity witness broadcast for aggression against inanimate objects (KER-18).

When the player smashes a shutter, a window, or any other inanimate
target in view of watchmen NPCs, the ordinary dialogue / retaliation
pipeline never fires — there is no NPC target, so no mood flip is
observed and :class:`cast.director_retaliation.RetaliationHandler`
silently skips the witnesses. This left guards standing ten feet away
frozen through repeated vandalism in the Ancient Rome playtest.

This module adds a lightweight per-turn channel for "someone watched
you do this":

* :class:`WitnessedAggression` is a frozen Pydantic record that flows
  through :class:`cast.schemas.turn_outputs.TurnOutputs` so it reaches
  the NPC turn prompt and can be asserted in tests.
* :func:`build_object_smash_witness` constructs one from the existing
  ``ItemGenerator`` delta text and the player action string.
* :func:`is_guard_occupation` classifies an NPC card as a watcher by
  matching occupation substrings against
  :data:`GUARD_OCCUPATION_KEYWORDS`.
* :func:`bump_guard_moods` flips neutral-mood guard witnesses to
  ``"threatened"`` so the existing aggression-roll pipeline (see
  ``cast/dice.py::AGGRESSION_THRESHOLDS``) wakes up on subsequent
  turns without a bespoke retaliation call. ``"threatened"`` is the
  only semantically accurate mood that is also a registered aggression
  threshold — ``"alarmed"`` is deliberately avoided because it is
  absent from ``AGGRESSION_THRESHOLDS`` and would silently no-op.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from models.game_state import GameState

GUARD_OCCUPATION_KEYWORDS: frozenset[str] = frozenset(
    (
        "guard",
        "watchman",
        "watch",
        "sentry",
        "centurion",
        "patrol",
        "legionary",
    ),
)

WITNESS_MOOD_THREATENED = "threatened"
WITNESS_KIND_OBJECT_SMASH = "object_smash"
WITNESS_KIND_NPC_ATTACK = "npc_attack"
_NEUTRAL_MOOD = "neutral"


class WitnessedAggression(BaseModel):
    """A per-turn record of aggressive player behaviour witnessed by NPCs.

    Attached to :class:`cast.schemas.turn_outputs.TurnOutputs` so it
    flows through the Director's turn pipeline. Frozen because the
    payload is a snapshot of a single turn and must not mutate between
    the object-interaction branch and the NPC-turn resolver.
    """

    model_config = ConfigDict(frozen=True)

    kind: str
    target: str
    location_id: str | None
    description: str


def is_guard_occupation(occupation: str | None) -> bool:
    """Return ``True`` when the occupation names a watcher-type role.

    The match is case-insensitive and substring-based so variants like
    ``"city guard"``, ``"night watchman"``, and ``"Praetorian guard"``
    all qualify. ``None`` and empty occupations return ``False``.
    """
    if not occupation:
        return False
    lowered = occupation.lower()
    return any(keyword in lowered for keyword in GUARD_OCCUPATION_KEYWORDS)


def build_object_smash_witness(
    target: str,
    delta_text: str,
    player_action: str,
    location_id: str | None,
) -> WitnessedAggression:
    """Build a :class:`WitnessedAggression` for an aggressive object INTERACT.

    ``delta_text`` is the persistent state change returned by the
    ItemGenerator in interact mode — it already reads as prose
    ("The front shutter hangs splintered and broken."). We prefix it
    with the raw player action so the NPC prompt has both the intent
    ("smash the shutter") and the result ("shutter hangs splintered")
    to react to.
    """
    description = _format_witness_description(player_action, delta_text)
    return WitnessedAggression(
        kind=WITNESS_KIND_OBJECT_SMASH,
        target=target,
        location_id=location_id,
        description=description,
    )


def _format_witness_description(player_action: str, delta_text: str) -> str:
    """Combine the player action and the object delta into a prompt line."""
    action = (player_action or "").strip()
    delta = (delta_text or "").strip()
    if action and delta:
        return "{0}. {1}".format(action.rstrip("."), delta)
    return action or delta


def build_npc_attack_witness(
    target_name: str,
    player_action: str,
    location_id: str | None,
) -> WitnessedAggression:
    """Build a :class:`WitnessedAggression` for an aggressive NPC INTERACT (KER-33).

    Parallel to :func:`build_object_smash_witness` but for the NPC
    target case: when the player punches or otherwise physically
    attacks a scene NPC, guards standing in the same room need the
    same "someone watched you do this" channel so their mood flips to
    ``"threatened"`` and the NPC-turn prompt sees the incident clause.
    """
    action = (player_action or "").strip() or "attacked"
    description = "{0} attacked {1}.".format(action.rstrip("."), target_name) if target_name else action
    return WitnessedAggression(
        kind=WITNESS_KIND_NPC_ATTACK,
        target=target_name,
        location_id=location_id,
        description=description,
    )


def _eligible_for_bump(npc: object) -> bool:
    """Return ``True`` when ``npc`` is a neutral-mood guard witness.

    Extracted so :func:`bump_guard_moods` stays well under the WPS231
    cognitive-complexity budget — the predicate is purely local to the
    mood-bump decision and has no call sites elsewhere.
    """
    occupation = getattr(npc, "occupation", None)
    if not is_guard_occupation(occupation):
        return False
    current = getattr(npc, "current_mood", "") or ""
    return current.lower() == _NEUTRAL_MOOD


def bump_guard_moods(
    game_state: GameState,
    witness_uuids: list[str],
    new_mood: str = WITNESS_MOOD_THREATENED,
) -> list[str]:
    """Flip ``current_mood`` to ``new_mood`` for neutral guard witnesses.

    Only NPCs whose current mood is exactly ``"neutral"`` are bumped,
    so an already-hostile or -enraged guard is never de-escalated. The
    occupation filter reuses :func:`is_guard_occupation` so tailors
    and beggars in the same scene are untouched.

    Returns the list of UUIDs that were actually bumped, useful for
    logging or test assertions.
    """
    bumped: list[str] = []
    for uuid in witness_uuids:
        npc = game_state.npcs.get(uuid)
        if npc is None or not _eligible_for_bump(npc):
            continue
        npc.current_mood = new_mood
        bumped.append(uuid)
    return bumped
