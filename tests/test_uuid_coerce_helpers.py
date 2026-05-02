"""Unit pins for the two narrowing helpers introduced by the UUID migration.

* :func:`cast._scene_location.coerce_scene_location_id` rewrites the
  Scene Builder's legacy ``"unknown"`` sentinel and unparseable LLM
  output into the all-zero ``UUID(int=0)``. Without this, the LLM
  emitting a malformed ``location_id`` would raise ``ValidationError``
  at scene parse time and abort the turn.
* :func:`timeline._uuid_coerce.coerce_uuid` narrows JSON-roundtripped
  ``effect_data`` values into ``uuid.UUID`` at the ``EffectApplier``
  boundary, treating ``None`` and ``""`` as "missing" and parsing real
  strings.
"""

from __future__ import annotations

import allure
import pytest

from cast._scene_location import UNKNOWN_SCENE_LOCATION, coerce_scene_location_id
from tests._log_helpers import capture_warnings
from tests._uuid_helpers import make_uuid
from timeline._uuid_coerce import coerce_uuid

_SAMPLE_UUID = make_uuid("uuid-coerce-helpers-sample")


@allure.epic("Scene & Exploration")
@allure.feature("Scene Builder")
@allure.story("Coerce scene location_id")
class TestCoerceSceneLocationId:
    """``coerce_scene_location_id`` collapses LLM output to a real UUID."""

    @allure.title("Passes a real UUID through unchanged")
    def test_passthrough_for_real_uuid(self) -> None:
        assert coerce_scene_location_id(_SAMPLE_UUID) is _SAMPLE_UUID

    @allure.title("Parses a canonical UUID string into a UUID")
    def test_parses_uuid_string(self) -> None:
        assert coerce_scene_location_id(str(_SAMPLE_UUID)) == _SAMPLE_UUID

    @allure.title("Empty input collapses to the all-zero sentinel")
    def test_empty_string_yields_sentinel(self) -> None:
        assert coerce_scene_location_id("") == UNKNOWN_SCENE_LOCATION

    @allure.title("None input collapses to the all-zero sentinel")
    def test_none_yields_sentinel(self) -> None:
        assert coerce_scene_location_id(None) == UNKNOWN_SCENE_LOCATION

    @allure.title("Legacy 'unknown' sentinel collapses to the all-zero UUID")
    def test_legacy_unknown_yields_sentinel(self) -> None:
        assert coerce_scene_location_id("unknown") == UNKNOWN_SCENE_LOCATION

    @allure.title("Garbage non-UUID string collapses to the all-zero UUID")
    def test_garbage_string_yields_sentinel(self) -> None:
        assert coerce_scene_location_id("not-a-uuid") == UNKNOWN_SCENE_LOCATION

    @allure.title("Garbage input emits an operator-visible warning; sentinel paths stay silent")
    def test_garbage_input_warns_but_silent_paths_dont(self) -> None:
        with capture_warnings() as messages:
            coerce_scene_location_id("not-a-uuid")
            coerce_scene_location_id("")
            coerce_scene_location_id("unknown")
            coerce_scene_location_id(None)
        assert any("not-a-uuid" in message for message in messages)
        assert sum("unparseable" in message for message in messages) == 1


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
