"""Consumer-side guard: the web client draws an icon for every backend slug.

The player UI renders location types and times of day as inline-SVG icons
(ADR-0018) instead of printing the English slugs. These tests read the icon
tables out of the shipped ``app.js`` and compare their keys to the
vocabularies the backend actually emits, so a new slug cannot silently render
without an icon.
"""

from __future__ import annotations

import re
from pathlib import Path

import allure

from models.game_state import GameState
from models.location import LOCATION_TYPES

pytestmark = [
    allure.epic("Player Interfaces"),
    allure.feature("Web UI"),
]

_APP_JS = Path(__file__).resolve().parents[1] / "interfaces" / "web" / "static" / "app.js"
_HOURS_PER_DAY = 24


def _icon_table_keys(table_name: str) -> set[str]:
    script = _APP_JS.read_text(encoding="utf-8")
    table = re.search(r"const {0} = \{{(.*?)\n  \}};".format(table_name), script, re.DOTALL)
    assert table is not None, "{0} not found in app.js".format(table_name)
    return set(re.findall(r"^\s+(\w+): svg\(", table.group(1), re.MULTILINE))


@allure.story("Static shell")
@allure.title("Static web client draws an icon for every location type the backend normalises to")
def test_place_icons_cover_location_types() -> None:
    assert _icon_table_keys("PLACE_ICONS") == set(LOCATION_TYPES)


@allure.story("Static shell")
@allure.title("Static web client draws an icon for every time-of-day label the game clock produces")
def test_daypart_icons_cover_game_clock_labels(game_state: GameState) -> None:
    labels = set()
    for _ in range(_HOURS_PER_DAY):
        game_state.advance_clock(1)
        labels.add(game_state.game_time)
    assert _icon_table_keys("DAYPART_ICONS") == labels
