"""Scoring rubric for the scene-builder re-entry-consistency benchmark.

Three deterministic checks compare the Forum's POI list across snapshots
(landmarks must persist with the same primary names, no duplicates on
re-entry) and confirm the re-entry narration names at least one seeded
landmark — an alias-aware membership test that needs no LLM judge. One
evidence-LLM check remains for the genuinely subjective question of
whether the re-entry prose contradicts the first visit's atmosphere
without an in-fiction reason.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Mapping

from benchmarks.harness.types._captures import CapturedTurn
from benchmarks.harness.types._elements import (
    KIND_DETERMINISTIC,
    KIND_EVIDENCE_LLM,
    DeterministicResult,
    Element,
    EvidencePromptSpec,
)
from benchmarks.scenarios._shared import EVIDENCE_QUOTE_CHAR_BUDGET
from benchmarks.scenarios.scene_builder_re_entry_consistency.state import FORUM_POIS, FORUM_UUID
from models.game_state import GameState

_RE_ENTRY_TURN_INDEX = 3
_SCENARIO_BRIEF = (
    "The player starts in the Forum Romanum (seeded with three landmarks: the rostra, the Temple "
    "of Saturn, and the Basilica Julia), walks south down the Vicus Tuscus for two turns, then "
    "returns to the Forum. The fourth captured turn is the re-entry — its narration is what the "
    "judges are reading. There were no in-fiction events that would alter the Forum (no fire, no "
    "construction, no demolition) between the first visit and the return."
)


def _forum_poi_names(snapshot: GameState) -> list[str]:
    """Return the Forum's POI primary names from a snapshot, or empty if the location is gone."""
    forum = snapshot.locations.get(FORUM_UUID)
    if forum is None:
        return []
    return [poi.names[0] for poi in forum.points_of_interest if poi.names]


def _landmarks_persist(
    _captured: list[CapturedTurn],
    snapshots: list[GameState],
) -> DeterministicResult:
    """Final Forum snapshot contains every seeded landmark name.

    A SceneBuilder pass that renames ``Temple of Saturn`` to
    ``Temple of Jupiter`` or drops the rostra entirely would fail
    here. We compare primary names rather than full alias lists so
    a legitimate alias-list expansion still passes.
    """
    if not snapshots:
        return DeterministicResult(awarded=0, reason="no snapshots captured")
    final_names = set(_forum_poi_names(snapshots[-1]))
    if not final_names:
        return DeterministicResult(awarded=0, reason="Forum location missing from final snapshot")
    seeded = set(FORUM_POIS)
    missing = sorted(seeded - final_names)
    if missing:
        return DeterministicResult(
            awarded=0,
            reason="Forum POIs went missing after re-entry: {0}".format(missing),
        )
    return DeterministicResult(
        awarded=3,
        reason="all seeded Forum landmarks persisted across the round trip",
    )


def _landmarks_not_duplicated(
    _captured: list[CapturedTurn],
    snapshots: list[GameState],
) -> DeterministicResult:
    """Forum POI list length did not grow due to re-entry duplication.

    The SceneBuilder's merge path is expected to dedupe — a rebuild
    that appends a second ``rostra`` POI on re-entry is a regression.
    """
    if len(snapshots) < 2:
        return DeterministicResult(awarded=0, reason="need at least two snapshots")
    initial_names = _forum_poi_names(snapshots[0])
    final_names = _forum_poi_names(snapshots[-1])
    if not initial_names or not final_names:
        return DeterministicResult(awarded=0, reason="Forum location missing in one snapshot")
    duplicates = sorted({name for name in final_names if final_names.count(name) > 1})
    if duplicates:
        return DeterministicResult(
            awarded=0,
            reason="duplicate Forum POIs after re-entry: {0}".format(duplicates),
            evidence_quote=", ".join(duplicates)[:EVIDENCE_QUOTE_CHAR_BUDGET],
        )
    if len(final_names) > len(initial_names):
        return DeterministicResult(
            awarded=1,
            reason="Forum POI count grew without duplicate primary names ({0} → {1})".format(
                len(initial_names),
                len(final_names),
            ),
        )
    return DeterministicResult(
        awarded=2,
        reason="Forum POI count stable across the round trip ({0})".format(len(initial_names)),
    )


# Lowercased phrases the narrator may use for each seeded landmark. The primary
# name is always included; common paraphrases are added so a re-entry that names
# a landmark indirectly ("Saturn's temple", "the speakers' platform") is not
# scored as a false regression — the previous evidence prompt recognised these too.
_LANDMARK_ALIASES: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "rostra": ("rostra", "rostrum", "speakers' platform", "speaker's platform", "orators' platform"),
        "Temple of Saturn": ("temple of saturn", "saturn's temple", "saturn temple"),
        "Basilica Julia": ("basilica julia", "julia basilica"),
    },
)


def _aliases_for(poi: str) -> tuple[str, ...]:
    """Lowercased aliases for a seeded POI, defaulting to its own lowercased name."""
    return _LANDMARK_ALIASES.get(poi, (poi.lower(),))


def _mentions_landmark(narration: str, poi: str) -> bool:
    """Whether the lowercased narration contains any alias of ``poi``."""
    return any(alias in narration for alias in _aliases_for(poi))


def _re_entry_names_landmark(
    captured: list[CapturedTurn],
    _snapshots: list[GameState],
) -> DeterministicResult:
    """Re-entry narration names at least one seeded Forum landmark.

    The element's proposition is a membership test over the seeded ``FORUM_POIS``
    against the re-entry turn's narration — a fact the LLM judges agreed on but
    that needs no judge. Matching is alias-aware (``_LANDMARK_ALIASES``) so a
    valid paraphrase still scores; a narration that opens on an unrelated set of
    features (as if the player had never visited the Forum) names none and scores 0.
    """
    if _RE_ENTRY_TURN_INDEX >= len(captured):
        return DeterministicResult(awarded=0, reason="re-entry turn was not captured")
    narration = captured[_RE_ENTRY_TURN_INDEX].narration.lower()
    mentioned = [poi for poi in FORUM_POIS if _mentions_landmark(narration, poi)]
    if mentioned:
        return DeterministicResult(
            awarded=2,
            reason="re-entry narration names seeded landmark(s): {0}".format(mentioned),
            evidence_quote=", ".join(mentioned)[:EVIDENCE_QUOTE_CHAR_BUDGET],
        )
    return DeterministicResult(
        awarded=0,
        reason="re-entry narration names none of the seeded Forum landmarks (incl. aliases)",
    )


ELEMENTS: tuple[Element, ...] = (
    Element(
        id="landmarks_persist",
        label="Seeded Forum landmarks (rostra, Temple of Saturn, Basilica Julia) survive re-entry",
        base_value=3,
        kind=KIND_DETERMINISTIC,
        check=_landmarks_persist,
    ),
    Element(
        id="landmarks_not_duplicated",
        label="Forum POI list does not duplicate on re-entry",
        base_value=2,
        kind=KIND_DETERMINISTIC,
        check=_landmarks_not_duplicated,
    ),
    Element(
        id="prose_consistent_on_return",
        label="Re-entry narration mentions at least one seeded Forum landmark",
        base_value=2,
        kind=KIND_DETERMINISTIC,
        check=_re_entry_names_landmark,
    ),
    Element(
        id="no_contradictory_redescription",
        label="Re-entry narration does not contradict the first visit's atmosphere",
        base_value=1,
        kind=KIND_EVIDENCE_LLM,
        check=EvidencePromptSpec(
            scenario_brief=_SCENARIO_BRIEF,
            question=(
                "Comparing the re-entry narration (turn 3) to the first-visit narration (turn 0), "
                "does the re-entry avoid contradicting the first visit's prose (e.g. switching "
                "from a crowded forum to a deserted one, from paved flagstones to dirt, from "
                "midday to night) without a justified in-fiction reason in the captured text?"
            ),
            evidence_turn=None,
        ),
    ),
)
