"""Emotional charge presets, value-axis signatures, and read-time decay.

Mirrors :mod:`knowledge.salience`: every ``PERSONAL_EXPERIENCE``
construction site reaches in here for a :class:`ChargePreset` instead of
hard-coding literals, so the Dwarf-Fortress-style emotional weighting is
tuned in one place. A charge has three parts:

* ``base_valence`` — the values-neutral signed feeling in ``[-1, 1]``
  (negative = bad), the same for every witness.
* ``base_intensity`` — how strongly felt in ``[0, 1]`` *before* decay.
* ``category`` — a key into :data:`AXIS_SIGNATURES`; the per-witness
  deriver colours ``base_valence`` by the witnessing NPC's values vector
  at read time, so one shared co-witnessed node yields a different felt
  valence per witness without storing per-witness copies.

Decay is lazy / read-time only and reuses the linear recency shape from
:func:`knowledge.query._memory_score` (``RECENCY_TAU_HOURS = 72.0``); it
attenuates intensity toward zero and never flips the sign of valence. No
LLM is involved in any number here.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import NamedTuple

RECENCY_TAU_HOURS = 72.0
_FLOAT_ZERO = float(0)
_FULL_RECENCY = float(1)
_VALENCE_MIN = float(-1)
_VALENCE_MAX = float(1)

# Named magnitudes so the presets/signatures read as tuned constants
# rather than scattered magic numbers (mirrors knowledge.salience).
_FULL = float(1)
_HALF = 0.5
_COMBAT_VALENCE = -0.8
_COMBAT_INTENSITY = 0.85
_RETALIATION_VALENCE = -0.6
_RETALIATION_INTENSITY = 0.85
_ROUTINE_VALENCE = _FLOAT_ZERO
_ROUTINE_INTENSITY = 0.2

# Value-axis names — must match the field names on
# :class:`models.values_vector.ValuesVector`.
LAW = "law"
KINSHIP = "kinship"
HONOR = "honor"
WEALTH = "wealth"
FAITH = "faith"
VALOR = "valor"
TRADITION = "tradition"

# Charge-category keys. The empty string is the neutral category with no
# value-axis relevance; it is also the field default on
# :class:`knowledge.node.KnowledgeNode`.
NEUTRAL_CATEGORY = ""
VIOLENCE = "violence"
RETALIATION_CATEGORY = "retaliation"
ROUTINE = "routine"


class ChargePreset(NamedTuple):
    """A reusable emotional-charge stamp for a class of event."""

    base_valence: float
    base_intensity: float
    category: str


# Signed relevance of each event category to each value axis: ``> 0`` the
# event upholds the axis, ``< 0`` it violates it. A law-valuing NPC
# (``values_vector.law > 0``) witnessing VIOLENCE (``law: -1``) feels it
# more negatively through the dot product in :func:`values_adjusted_valence`.
AXIS_SIGNATURES: MappingProxyType[str, MappingProxyType[str, float]] = MappingProxyType(
    {
        VIOLENCE: MappingProxyType({LAW: -_FULL, VALOR: -_HALF, KINSHIP: -_HALF}),
        RETALIATION_CATEGORY: MappingProxyType({VALOR: _HALF, LAW: -_HALF}),
        ROUTINE: MappingProxyType({}),
    },
)

# Presets — names mirror :mod:`knowledge.salience`.
COMBAT = ChargePreset(base_valence=_COMBAT_VALENCE, base_intensity=_COMBAT_INTENSITY, category=VIOLENCE)
RETALIATION = ChargePreset(
    base_valence=_RETALIATION_VALENCE,
    base_intensity=_RETALIATION_INTENSITY,
    category=RETALIATION_CATEGORY,
)
ROUTINE_DIALOGUE = ChargePreset(base_valence=_ROUTINE_VALENCE, base_intensity=_ROUTINE_INTENSITY, category=ROUTINE)
NEUTRAL = ChargePreset(base_valence=_FLOAT_ZERO, base_intensity=_FLOAT_ZERO, category=NEUTRAL_CATEGORY)


def decayed_intensity(charge_intensity: float, timestamp: float | None, now: float) -> float:
    """Attenuate ``charge_intensity`` by linear recency decay.

    Mirrors the recency factor in :func:`knowledge.query._memory_score`:
    linear over :data:`RECENCY_TAU_HOURS`, clamped at zero, with a
    missing timestamp contributing nothing. Decay is computed against the
    passed game clock ``now`` (not the freshest-pool reference the query
    engine uses), so an absolute-clock read is stable and reproducible.
    """
    if timestamp is None:
        return _FLOAT_ZERO
    age = max(_FLOAT_ZERO, now - timestamp)
    recency = max(_FLOAT_ZERO, _FULL_RECENCY - age / RECENCY_TAU_HOURS)
    return charge_intensity * recency


def values_adjusted_valence(base_valence: float, category: str, value_weights: object) -> float:
    """Colour ``base_valence`` by a witness's values vector (read time).

    Adds the dot product of the event category's axis signature with the
    witness's value weights to the base valence, then clamps to
    ``[-1, 1]``. An unknown or neutral category leaves the base valence
    untouched (bar clamping). ``value_weights`` is duck-typed against the
    axis names so the knowledge layer need not import the model.
    """
    signature = AXIS_SIGNATURES.get(category)
    if not signature:
        return _clamp_valence(base_valence)
    return _clamp_valence(base_valence + _axis_gain(signature, value_weights))


def _axis_gain(signature: MappingProxyType[str, float], value_weights: object) -> float:
    """Dot product of an axis signature with a witness's value weights."""
    return sum(_axis_term(value_weights, pair) for pair in signature.items())


def _axis_term(value_weights: object, axis_relevance: tuple[str, float]) -> float:
    axis, relevance = axis_relevance
    return float(getattr(value_weights, axis, _FLOAT_ZERO)) * relevance


def _clamp_valence(raw_valence: float) -> float:
    return max(_VALENCE_MIN, min(_VALENCE_MAX, raw_valence))
