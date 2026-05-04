from __future__ import annotations

from uuid import uuid4

import allure

from cast.narrator import _resolve_current_location
from db.converters.location import location_to_row
from engine.location_init import materialise_setting_locations
from knowledge.graph import KnowledgeGraph
from models.game_state import GameState
from models.location import Location
from models.setting import Setting

pytestmark = [allure.epic("Engine & LLM Infrastructure"), allure.feature("Location materialisation")]


def _make_game_state(*, locations: list[dict[str, str]] | None = None) -> GameState:
    setting = Setting(
        name="Rome",
        time_period="1300",
        region="Italy",
        summary="Eternal city",
        locations=locations or [],
    )
    return GameState(setting=setting, knowledge_graph=KnowledgeGraph())


@allure.story("Setting → Location promotion")
@allure.title("materialise_setting_locations creates one Location per setting entry with a real UUID")
def test_materialise_creates_location_per_setting_entry() -> None:
    game_state = _make_game_state(
        locations=[
            {"name": "Forum", "type": "district", "description": "Open square"},
            {"name": "Colosseum", "type": "building", "description": "Amphitheatre"},
        ],
    )

    materialise_setting_locations(game_state)

    assert len(game_state.locations) == 2
    by_name = {loc.name: loc for loc in game_state.locations.values()}
    assert by_name["Forum"].description == "Open square"
    assert by_name["Forum"].location_type == "district"
    assert by_name["Colosseum"].location_type == "building"
    for loc in game_state.locations.values():
        assert loc.uuid in game_state.locations


@allure.story("Player anchor")
@allure.title("materialise_setting_locations sets player.location_id to the first materialised entry")
def test_materialise_assigns_player_to_first_location() -> None:
    game_state = _make_game_state(
        locations=[
            {"name": "Forum", "type": "district", "description": ""},
            {"name": "Colosseum", "type": "building", "description": ""},
        ],
    )

    materialise_setting_locations(game_state)

    forum_uuid = next(loc.uuid for loc in game_state.locations.values() if loc.name == "Forum")
    assert game_state.player.location_id == forum_uuid


@allure.story("Player anchor")
@allure.title("Player location_id resolves to a Location entry registered in game_state.locations")
def test_player_location_id_resolves_in_locations_dict() -> None:
    game_state = _make_game_state(
        locations=[{"name": "Forum", "type": "district", "description": ""}],
    )

    materialise_setting_locations(game_state)

    assert game_state.player.location_id is not None
    assert game_state.player.location_id in game_state.locations


@allure.story("Skip blank entries")
@allure.title("materialise_setting_locations skips entries with empty or whitespace-only names")
def test_materialise_skips_blank_name_entries() -> None:
    game_state = _make_game_state(
        locations=[
            {"name": "", "type": "x", "description": "y"},
            {"name": "   ", "type": "x", "description": "y"},
            {"name": "Forum", "type": "district", "description": ""},
        ],
    )

    materialise_setting_locations(game_state)

    assert [loc.name for loc in game_state.locations.values()] == ["Forum"]


@allure.story("Categorical slug invariant")
@allure.title("materialise_setting_locations falls back to 'generic' for off-enum location_type values")
def test_materialise_collapses_unknown_location_type_to_generic() -> None:
    """Regression: DataMiner can emit freeform phrases (esp. for non-English settings, e.g.
    'религиозное общественное сооружение') that both overflow locations.location_type varchar(32)
    and silently misroute knowledge.rumor_scope's city-anchor walk, which compares to the slug "city".
    Off-enum values must collapse to "generic".
    """
    game_state = _make_game_state(
        locations=[{"name": "Храм", "type": "религиозное общественное сооружение", "description": ""}],
    )

    materialise_setting_locations(game_state)

    loc = next(iter(game_state.locations.values()))
    assert loc.location_type == "generic"


@allure.story("Categorical slug invariant")
@allure.title("location_to_row emits an enum-valid location_type for the DB INSERT")
def test_location_to_row_writes_enum_valid_location_type() -> None:
    """Consumer-seam check: even if a future caller bypasses materialisation (or uses model_construct),
    the row handed to locations.location_type must be a known categorical slug — not a freeform phrase.
    """
    loc = Location(name="Храм", location_type="религиозное общественное сооружение")
    row = location_to_row(loc, game_state_id=str(uuid4()))

    assert row["location_type"] == "generic"


@allure.story("Defaults")
@allure.title("materialise_setting_locations defaults location_type to 'generic' when type is missing or blank")
def test_materialise_defaults_location_type() -> None:
    game_state = _make_game_state(
        locations=[
            {"name": "Forum", "description": "no type field"},
            {"name": "Colosseum", "type": "", "description": "blank type"},
        ],
    )

    materialise_setting_locations(game_state)

    for loc in game_state.locations.values():
        assert loc.location_type == "generic"


@allure.story("Idempotence")
@allure.title("materialise_setting_locations is a no-op when game_state.locations is already populated")
def test_materialise_no_op_when_locations_already_populated() -> None:
    """Restored sessions arrive with locations already loaded; do not duplicate or re-anchor the player."""
    game_state = _make_game_state(
        locations=[{"name": "Forum", "type": "district", "description": ""}],
    )
    pre_existing = Location(uuid=uuid4(), name="Tavern")
    game_state.locations[pre_existing.uuid] = pre_existing
    original_player_location = game_state.player.location_id

    materialise_setting_locations(game_state)

    assert list(game_state.locations.keys()) == [pre_existing.uuid]
    assert game_state.player.location_id == original_player_location


@allure.story("Empty setting")
@allure.title("materialise_setting_locations leaves player.location_id None when the setting carries no locations")
def test_materialise_empty_setting_leaves_player_unanchored() -> None:
    game_state = _make_game_state(locations=[])

    materialise_setting_locations(game_state)

    assert game_state.locations == {}
    assert game_state.player.location_id is None


@allure.story("Consumer seam: Narrator")
@allure.title("Narrator._resolve_current_location returns the materialised Location, not None")
def test_narrator_resolves_materialised_location() -> None:
    """Without materialisation, the Narrator falls through to ``None`` and silently drops prior-damage surfacing."""
    game_state = _make_game_state(
        locations=[{"name": "Forum", "type": "district", "description": "Open square"}],
    )

    materialise_setting_locations(game_state)
    resolved = _resolve_current_location(game_state)

    assert resolved is not None
    assert resolved.name == "Forum"
    assert resolved.uuid == game_state.player.location_id
