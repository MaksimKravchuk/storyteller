"""Presence-window resolution for phase-1 scene summarisation (G4).

``_first_appearance_index`` resolves an NPC's first log appearance via
two branches: it acts (``actor_uuid``) OR it is named in an event's
``metadata['witness_ids']`` (stored stringified, JSONB-safe). The
``consolidate_scene`` tests only ever exercise the ``actor_uuid``
branch; a witness-only NPC (named in an event but never acting) takes
the untested branch, where a bug would silently drop or mis-scope its
summary.
"""

from __future__ import annotations

import allure

from knowledge.scene_summary_phase import _first_appearance_index, _presence_start_index
from models.scene_action_log import ActorKind, SceneActionEntry
from tests._uuid_helpers import make_uuid

pytestmark = [
    allure.epic("NPC short-term memory"),
    allure.feature("Presence-window scoping"),
]

_WITNESS = make_uuid("witness-npc")
_ACTOR = make_uuid("acting-npc")


def _player(clock: float, text: str) -> SceneActionEntry:
    return SceneActionEntry(
        actor_kind=ActorKind.PLAYER,
        actor_uuid=make_uuid("player"),
        actor_name="Player",
        action_type="TALK",
        description=text,
        game_clock=clock,
    )


def _witnessed_event(clock: float, witness_uuids: list) -> SceneActionEntry:
    return SceneActionEntry(
        actor_kind=ActorKind.EVENT,
        actor_uuid=None,
        actor_name="",
        action_type="WITNESS",
        description="A blade is drawn.",
        game_clock=clock,
        metadata={"witness_ids": [str(uid) for uid in witness_uuids]},
    )


@allure.story("G4")
@allure.title("An NPC whose only appearance is an event's witness_ids resolves via the witness branch")
def test_witness_only_first_appearance() -> None:
    entries = [
        _player(1.0, "I greet the room."),
        _witnessed_event(1.0, [_WITNESS]),
        _player(2.0, "I leave."),
    ]

    assert _first_appearance_index(entries, _WITNESS) == 1
    # The whole first turn (clock 1.0) is in-scope: the start walks
    # back to the player utterance the NPC witnessed, not the event.
    assert _presence_start_index(entries, _WITNESS) == 0


@allure.story("G4")
@allure.title("The acting branch still resolves, and an absent NPC yields None")
def test_actor_branch_and_absent() -> None:
    acting = SceneActionEntry(
        actor_kind=ActorKind.NPC,
        actor_uuid=_ACTOR,
        actor_name="Marcus",
        action_type="ATTACK",
        description="Marcus lunges.",
        game_clock=3.0,
        significant=True,
    )
    entries = [_player(3.0, "I draw steel."), acting]

    assert _first_appearance_index(entries, _ACTOR) == 1
    assert _presence_start_index(entries, _ACTOR) == 0
    assert _first_appearance_index(entries, make_uuid("never-here")) is None
    assert _presence_start_index(entries, make_uuid("never-here")) is None
