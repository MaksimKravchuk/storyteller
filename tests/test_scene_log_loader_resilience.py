"""Loader resilience for the scene_action_log JSONB column (G1).

``SceneActionEntry`` grew a ``model_validator`` that rejects the
actor-identity matrix. The loader rebuilds every entry via
``SceneActionEntry(**raw)``, so a row written before the validator
landed (e.g. a PLAYER entry with no ``actor_uuid``) would otherwise
raise ``ValidationError`` and brick the *entire session load*. The
scene log is enrichment data — a malformed entry must be dropped
loudly, not propagated.
"""

from __future__ import annotations

import allure

from db.repo_loader_helpers import _hydrate_scene_action_log
from models.scene_action_log import ActorKind
from tests._uuid_helpers import make_uuid

pytestmark = [
    allure.epic("Memory & Persistence"),
    allure.feature("Scene action log loader"),
]


def _valid_player_row() -> dict:
    return {
        "actor_kind": ActorKind.PLAYER.value,
        "actor_uuid": str(make_uuid("player")),
        "actor_name": "Player",
        "action_type": "TALK",
        "description": "I greet the guard.",
        "game_clock": 1.0,
    }


def _legacy_player_row_without_uuid() -> dict:
    """A pre-validator PLAYER row: no ``actor_uuid``. Now illegal."""
    return {
        "actor_kind": ActorKind.PLAYER.value,
        "actor_name": "Player",
        "action_type": "TALK",
        "description": "I greet the guard.",
        "game_clock": 1.0,
    }


@allure.story("G1")
@allure.title("A malformed legacy entry is dropped loudly; valid entries still load")
def test_malformed_entry_is_dropped_not_fatal(loguru_sink) -> None:
    rebuilt = _hydrate_scene_action_log([_legacy_player_row_without_uuid(), _valid_player_row()])

    # Session still loads: the one valid entry survives.
    assert len(rebuilt) == 1
    assert rebuilt[0].actor_kind == ActorKind.PLAYER
    assert rebuilt[0].description == "I greet the guard."

    # And the drop is loud, not silent.
    errors = [rec["message"] for rec in loguru_sink if rec["level"].name == "ERROR"]
    assert any("scene_action_log" in msg for msg in errors)


@allure.story("G1")
@allure.title("An all-valid log round-trips unchanged")
def test_all_valid_entries_load(loguru_sink) -> None:
    rebuilt = _hydrate_scene_action_log([_valid_player_row(), _valid_player_row()])

    assert len(rebuilt) == 2
    assert [rec for rec in loguru_sink if rec["level"].name == "ERROR"] == []


@allure.story("G1")
@allure.title("None / empty JSONB normalises to an empty list")
def test_none_and_empty_normalise() -> None:
    assert _hydrate_scene_action_log(None) == []
    assert _hydrate_scene_action_log([]) == []
