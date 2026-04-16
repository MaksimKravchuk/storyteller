"""Scenario types — the definition + seed-state for a benchmark run."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable

from benchmarks.harness.types._elements import Element

if TYPE_CHECKING:
    from models.game_state import GameState
    from timeline.event import GameEvent


@dataclass(frozen=True)
class ScriptTurn:
    """One scripted player action, with an optional human-readable note."""

    player_action: str
    note: str = ""


@dataclass(frozen=True)
class Scenario:
    """A complete benchmark scenario."""

    id: str
    label: str
    build_state: Callable[[], "ScenarioState"]
    script: Sequence[ScriptTurn]
    elements: Sequence[Element]

    def __post_init__(self) -> None:
        if not self.script:
            raise ValueError("Scenario {0!r} must declare at least one script turn".format(self.id))
        if not self.elements:
            raise ValueError("Scenario {0!r} must declare at least one element".format(self.id))
        ids = [element.id for element in self.elements]
        if len(set(ids)) != len(ids):
            raise ValueError("Scenario {0!r} has duplicate element ids: {1}".format(self.id, ids))


@dataclass
class ScenarioState:
    """Seed state passed to ``engine.factory.create_engine_from_state``."""

    game_state: "GameState"
    events: list["GameEvent"] = field(default_factory=list)
