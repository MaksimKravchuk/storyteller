"""Scenario types — the definition + seed-state for a benchmark run."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable

from benchmarks.harness.types._elements import Element

if TYPE_CHECKING:
    from models.game_state import GameState


@dataclass(frozen=True)
class ScriptTurn:
    """One step in a scenario script.

    ``player_action`` is the raw string passed to ``engine.process_action``.
    ``note`` is free-form text recorded in the artefact for humans reading
    the report; it does not affect scoring.
    """

    player_action: str
    note: str = ""


@dataclass(frozen=True)
class Scenario:
    """A complete benchmark scenario.

    ``id`` is the filesystem-safe identifier used in artefact filenames.
    ``label`` is the human-readable name shown in reports.
    ``build_state`` constructs a fresh :class:`GameState` and pre-seeded
    :class:`KnowledgeGraph` on every iteration so runs never share
    mutable state. ``script`` is the ordered list of player actions.
    ``elements`` is the rubric scored against captured signals.
    """

    id: str
    label: str
    build_state: Callable[[], "ScenarioState"]
    script: Sequence[ScriptTurn]
    elements: Sequence[Element]


@dataclass
class ScenarioState:
    """Seed state returned by a scenario's ``build_state`` callable.

    Holds the three objects :func:`engine.factory.create_engine_from_state`
    needs to rehydrate a :class:`GameEngine` without running the
    DataMiner. ``events`` is separate from ``game_state`` because the
    existing ``restore_session`` entry-point takes the event list as its
    own argument.
    """

    game_state: "GameState"
    events: list = field(default_factory=list)
