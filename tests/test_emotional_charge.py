"""Deterministic charge presets, read-time decay, and node-field bounds."""

from __future__ import annotations

import allure
import pytest
from pydantic import ValidationError

from knowledge import charge
from knowledge.node import KnowledgeNode
from models.values_vector import ValuesVector

pytestmark = [
    allure.epic("NPC Interaction"),
    allure.feature("Emotional memory"),
]


@allure.story("Read-time decay")
class TestDecay:
    @allure.title("Charge intensity decays linearly to half over half the recency window")
    def test_intensity_decays_linearly(self):
        # now = half of tau → half intensity.
        assert charge.decayed_intensity(1.0, timestamp=0, now=36.0) == pytest.approx(0.5)

    @allure.title("Decay clamps to zero at and beyond the recency window")
    def test_decay_clamps_at_tau(self):
        assert charge.decayed_intensity(1.0, timestamp=0, now=72.0) == pytest.approx(0)
        assert charge.decayed_intensity(1.0, timestamp=0, now=200.0) == pytest.approx(0)

    @allure.title("Full intensity is returned when read at the creation clock")
    def test_full_intensity_at_creation_clock(self):
        assert charge.decayed_intensity(0.85, timestamp=10.0, now=10.0) == pytest.approx(0.85)

    @allure.title("A missing timestamp contributes zero recency")
    def test_missing_timestamp_zero_recency(self):
        assert charge.decayed_intensity(0.9, timestamp=None, now=5.0) == pytest.approx(0)

    @allure.title("A future-dated memory clamps age to zero (full intensity)")
    def test_future_memory_clamps_age_to_zero(self):
        # now < timestamp (clock skew): age floors at 0 → full intensity.
        assert charge.decayed_intensity(0.7, timestamp=10.0, now=5.0) == pytest.approx(0.7)

    @allure.title("Decay keys off the passed game clock, not a pool reference")
    def test_decay_uses_passed_clock_not_pool_reference(self):
        fresh = charge.decayed_intensity(1.0, timestamp=0, now=0)
        stale = charge.decayed_intensity(1.0, timestamp=0, now=36.0)
        assert fresh == pytest.approx(1.0)
        assert stale == pytest.approx(0.5)


@allure.story("Values-weighted valence")
class TestValuesAdjustedValence:
    @allure.title("A law-valuing witness feels witnessed violence more negatively")
    def test_law_valuing_witness_feels_violence_worse(self):
        base = charge.COMBAT.base_valence
        law_abider = charge.values_adjusted_valence(base, charge.VIOLENCE, ValuesVector(law=1.0))
        indifferent = charge.values_adjusted_valence(base, charge.VIOLENCE, ValuesVector())
        assert law_abider < indifferent

    @allure.title("An anti-law witness feels witnessed violence less badly")
    def test_outlaw_witness_feels_violence_less_badly(self):
        base = -0.5
        outlaw = charge.values_adjusted_valence(base, charge.VIOLENCE, ValuesVector(law=-1.0))
        assert outlaw > base

    @allure.title("Opposite values vectors land on opposite valence signs")
    def test_opposite_vectors_land_on_opposite_signs(self):
        base = 0
        pos = charge.values_adjusted_valence(base, charge.RETALIATION_CATEGORY, ValuesVector(valor=1.0))
        neg = charge.values_adjusted_valence(base, charge.RETALIATION_CATEGORY, ValuesVector(valor=-1.0))
        assert pos > 0
        assert neg < 0

    @allure.title("Values-weighted valence clamps to the [-1, 1] interval")
    def test_clamps_to_unit_interval(self):
        strong = ValuesVector(law=1.0, valor=1.0, kinship=1.0)
        assert charge.values_adjusted_valence(-0.9, charge.VIOLENCE, strong) == pytest.approx(-1.0)
        assert charge.values_adjusted_valence(0.9, charge.RETALIATION_CATEGORY, ValuesVector(valor=1.0)) <= 1

    @allure.title("The neutral category returns the base valence unchanged")
    def test_neutral_category_returns_base(self):
        adjusted = charge.values_adjusted_valence(-0.3, charge.NEUTRAL_CATEGORY, ValuesVector(law=1.0))
        assert adjusted == pytest.approx(-0.3)

    @allure.title("An unknown category returns the clamped base valence")
    def test_unknown_category_returns_clamped_base(self):
        assert charge.values_adjusted_valence(0.4, "no_such_category", ValuesVector(law=1.0)) == pytest.approx(0.4)


@allure.story("Node charge bounds")
class TestNodeChargeBounds:
    @allure.title("KnowledgeNode rejects valence outside [-1, 1]")
    def test_valence_bounds_rejected(self):
        with pytest.raises(ValidationError):
            KnowledgeNode(text="x", valence=2.0)
        with pytest.raises(ValidationError):
            KnowledgeNode(text="x", valence=-1.5)

    @allure.title("KnowledgeNode rejects charge_intensity outside [0, 1]")
    def test_charge_intensity_bounds_rejected(self):
        with pytest.raises(ValidationError):
            KnowledgeNode(text="x", charge_intensity=-0.1)
        with pytest.raises(ValidationError):
            KnowledgeNode(text="x", charge_intensity=1.5)

    @allure.title("KnowledgeNode charge fields default to neutral")
    def test_defaults_are_neutral(self):
        node = KnowledgeNode(text="x")
        assert node.valence == 0
        assert node.charge_intensity == 0
        assert node.charge_category == ""


@allure.story("Values vector bounds")
class TestValuesVectorBounds:
    @allure.title("ValuesVector rejects an axis weight outside [-1, 1]")
    def test_axis_bounds_rejected(self):
        with pytest.raises(ValidationError):
            ValuesVector(law=1.5)
        with pytest.raises(ValidationError):
            ValuesVector(honor=-1.5)

    @allure.title("ValuesVector defaults every axis to zero")
    def test_defaults_all_zero(self):
        vector = ValuesVector()
        for axis in ("law", "kinship", "honor", "wealth", "faith", "valor", "tradition"):
            assert getattr(vector, axis) == 0
