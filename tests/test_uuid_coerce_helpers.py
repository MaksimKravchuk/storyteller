"""Unit pins for the two narrowing helpers introduced by the UUID migration.

* :func:`cast._scene_location.resolve_scene_location_id` maps the Scene
  Builder's ``location_id`` onto a known place, and every other value
  (new snake_case key, ``"unknown"``, empty) onto the all-zero
  ``UUID(int=0)`` sentinel, so a free-form key never fails Scene parsing.
* :func:`timeline._uuid_coerce.coerce_uuid` narrows JSON-roundtripped
  ``effect_data`` values into ``uuid.UUID`` at the ``EffectApplier``
  boundary, treating ``None`` and ``""`` as "missing" and parsing real
  strings.
"""

from __future__ import annotations

import allure
import pytest

from cast._scene_location import UNKNOWN_SCENE_LOCATION
from cast.scene_place import place_key, resolve_scene_location_id
from tests._uuid_helpers import make_uuid
from timeline._uuid_coerce import coerce_uuid

_SAMPLE_UUID = make_uuid("uuid-coerce-helpers-sample")


@allure.epic("Scene & Exploration")
@allure.feature("Scene Builder")
@allure.story("Resolve scene location_id")
class TestResolveSceneLocationId:
    """``resolve_scene_location_id`` maps a known place id to its UUID, anything else to the sentinel."""

    @allure.title("A place's short key resolves to that place")
    def test_short_key_resolves_known_place(self) -> None:
        other = make_uuid("uuid-coerce-helpers-other")
        assert resolve_scene_location_id(place_key(_SAMPLE_UUID), [other, _SAMPLE_UUID]) == _SAMPLE_UUID

    @allure.title("The short key matches case-insensitively and ignores surrounding whitespace")
    def test_short_key_is_case_insensitive(self) -> None:
        raw = "  {0}  ".format(place_key(_SAMPLE_UUID).upper())
        assert resolve_scene_location_id(raw, [_SAMPLE_UUID]) == _SAMPLE_UUID

    @allure.title("A full UUID string of a known place resolves to that place")
    def test_full_uuid_string_resolves_known_place(self) -> None:
        assert resolve_scene_location_id(str(_SAMPLE_UUID), [_SAMPLE_UUID]) == _SAMPLE_UUID

    @allure.title("A new snake_case key resolves to the sentinel")
    def test_new_key_yields_sentinel(self) -> None:
        assert resolve_scene_location_id("upper_village_path", [_SAMPLE_UUID]) == UNKNOWN_SCENE_LOCATION

    @allure.title("A UUID that is not a known place resolves to the sentinel")
    def test_unknown_uuid_yields_sentinel(self) -> None:
        assert resolve_scene_location_id(str(_SAMPLE_UUID), []) == UNKNOWN_SCENE_LOCATION

    @allure.title("Empty and None input resolve to the sentinel")
    @pytest.mark.parametrize("raw", ["", "   ", None])
    def test_empty_yields_sentinel(self, raw: str | None) -> None:
        assert resolve_scene_location_id(raw, [_SAMPLE_UUID]) == UNKNOWN_SCENE_LOCATION

    @allure.title("place_key is the first eight hex digits of the UUID")
    def test_place_key_shape(self) -> None:
        assert place_key(_SAMPLE_UUID) == _SAMPLE_UUID.hex[:8]


@allure.epic("Game Timeline")
@allure.feature("Effect applier")
@allure.story("Coerce effect_data uuid")
class TestCoerceUuid:
    """``coerce_uuid`` narrows JSON-roundtripped values into ``uuid.UUID``."""

    @allure.title("Passes a real UUID through unchanged")
    def test_passthrough_for_real_uuid(self) -> None:
        assert coerce_uuid(_SAMPLE_UUID) is _SAMPLE_UUID

    @allure.title("Parses a canonical UUID string into a UUID")
    def test_parses_uuid_string(self) -> None:
        assert coerce_uuid(str(_SAMPLE_UUID)) == _SAMPLE_UUID

    @allure.title("None input returns None (field omitted)")
    def test_none_returns_none(self) -> None:
        assert coerce_uuid(None) is None

    @allure.title("Empty string returns None (field omitted)")
    def test_empty_string_returns_none(self) -> None:
        assert coerce_uuid("") is None

    @allure.title("Garbage non-empty input raises ValueError (corruption is loud)")
    def test_garbage_string_raises(self) -> None:
        with pytest.raises(ValueError):
            coerce_uuid("not-a-uuid")
