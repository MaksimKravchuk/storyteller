"""Schema validation tests for the Relationship model."""

from __future__ import annotations

import allure
import pytest
from pydantic import ValidationError

from models.relationship import Relationship, RelationshipKind


@allure.epic("Memory & Persistence")
@allure.feature("Relationship model")
class TestRelationshipKindCoercion:
    @allure.story("Kind coercion")
    @allure.title("A valid lowercase kind string is accepted and coerced to the enum member")
    def test_valid_kind_string_accepted(self):
        rel = Relationship(target_uuid="npc-1", kind="enemy")
        assert rel.kind == RelationshipKind.ENEMY

    @allure.story("Kind coercion")
    @allure.title("An uppercase kind string is normalised to the correct enum member")
    def test_kind_is_case_insensitive(self):
        rel = Relationship(target_uuid="npc-1", kind="ENEMY")
        assert rel.kind == RelationshipKind.ENEMY

    @allure.story("Kind coercion")
    @allure.title("Leading and trailing whitespace is stripped before enum coercion")
    def test_kind_strips_whitespace(self):
        rel = Relationship(target_uuid="npc-1", kind="  ally  ")
        assert rel.kind == RelationshipKind.ALLY

    @allure.story("Kind coercion")
    @allure.title("An unrecognised kind string (e.g. an LLM typo) falls back to NEUTRAL with no error")
    def test_unknown_kind_falls_back_to_neutral(self):
        rel = Relationship(target_uuid="npc-1", kind="muderous")
        assert rel.kind == RelationshipKind.NEUTRAL

    @allure.story("Kind coercion")
    @allure.title("Every valid RelationshipKind value is accepted as a kind string")
    def test_all_valid_kinds_accepted(self):
        for kind in RelationshipKind:
            rel = Relationship(target_uuid="npc-1", kind=kind)
            assert rel.kind == kind


@allure.epic("Memory & Persistence")
@allure.feature("Relationship model")
class TestRelationshipIntensity:
    @allure.story("Intensity bounds")
    @allure.title("Default intensity is 0 when not specified")
    def test_default_intensity_is_zero(self):
        rel = Relationship(target_uuid="npc-1", kind=RelationshipKind.NEUTRAL)
        assert rel.intensity == 0

    @allure.story("Intensity bounds")
    @allure.title("Minimum intensity of -3 is accepted")
    def test_min_intensity_accepted(self):
        rel = Relationship(target_uuid="npc-1", kind=RelationshipKind.ENEMY, intensity=-3)
        assert rel.intensity == -3

    @allure.story("Intensity bounds")
    @allure.title("Maximum intensity of +3 is accepted")
    def test_max_intensity_accepted(self):
        rel = Relationship(target_uuid="npc-1", kind=RelationshipKind.ALLY, intensity=3)
        assert rel.intensity == 3

    @allure.story("Intensity bounds")
    @allure.title("Intensity below -3 raises a ValidationError")
    def test_intensity_below_min_raises(self):
        with pytest.raises(ValidationError):
            Relationship(target_uuid="npc-1", kind=RelationshipKind.ENEMY, intensity=-4)

    @allure.story("Intensity bounds")
    @allure.title("Intensity above +3 raises a ValidationError")
    def test_intensity_above_max_raises(self):
        with pytest.raises(ValidationError):
            Relationship(target_uuid="npc-1", kind=RelationshipKind.ALLY, intensity=4)


@allure.epic("Memory & Persistence")
@allure.feature("Relationship model")
class TestRelationshipValidation:
    @allure.story("Schema validation")
    @allure.title("Omitting target_uuid raises a ValidationError")
    def test_missing_target_uuid_raises(self):
        with pytest.raises(ValidationError):
            Relationship(kind=RelationshipKind.ENEMY)  # type: ignore[call-arg]

    @allure.story("Schema validation")
    @allure.title("Omitting kind raises a ValidationError")
    def test_missing_kind_raises(self):
        with pytest.raises(ValidationError):
            Relationship(target_uuid="npc-1")  # type: ignore[call-arg]

    @allure.story("Schema validation")
    @allure.title("Optional fields default to empty string and None when not provided")
    def test_optional_fields_default_correctly(self):
        rel = Relationship(target_uuid="npc-1", kind=RelationshipKind.FRIEND)
        assert rel.note == ""
        assert rel.established_turn is None
        assert rel.source_thread_uuid is None

    @allure.story("Round-trip")
    @allure.title("Relationship round-trips through model_dump(mode=json) without losing any field")
    def test_round_trip_via_model_dump(self):
        rel = Relationship(
            target_uuid="npc-42",
            kind=RelationshipKind.ENEMY,
            intensity=-2,
            note="old grudge",
            established_turn=5,
        )
        dumped = rel.model_dump(mode="json")
        restored = Relationship.model_validate(dumped)
        assert restored.target_uuid == rel.target_uuid
        assert restored.kind == rel.kind
        assert restored.intensity == rel.intensity
        assert restored.note == rel.note
        assert restored.established_turn == rel.established_turn
