"""Reusable EvidencePromptSpec factories for prose-quality regression checks.

Each factory returns an :class:`EvidencePromptSpec` where **YES = good quality**.
A YES verdict must be backed by a verifiable quote from the turn text — an
unverifiable YES is converted to NO at scoring time. A NO verdict should ideally
quote the offending phrase, but an empty quote is permitted by the judge protocol.
Questions are phrased to make both YES quotes (fresh prose) and NO quotes
(the offending phrase) easy to find.
"""

from __future__ import annotations

from benchmarks.harness.types._elements import EvidencePromptSpec


def no_cliches(scenario_brief: str, evidence_turn: int | None = None) -> EvidencePromptSpec:
    """YES = narration avoids cinematic action-movie clichés on the targeted turn(s)."""
    return EvidencePromptSpec(
        scenario_brief=scenario_brief,
        question=(
            "Is the narration in this turn free of cinematic action-movie clichés such as "
            "'heart pounding', 'time stood still', 'adrenaline surged', 'world went dark', "
            "'blood ran cold', 'braced for impact', or similar stock phrases? "
            "Answer YES if the prose is fresh and specific. "
            "Answer NO if you can quote a recognisable clichéd stock phrase."
        ),
        evidence_turn=evidence_turn,
    )


def no_purple_prose(scenario_brief: str, evidence_turn: int | None = None) -> EvidencePromptSpec:
    """YES = narration avoids overwrought, melodramatic language on the targeted turn(s)."""
    return EvidencePromptSpec(
        scenario_brief=scenario_brief,
        question=(
            "Is the narration in this turn free of purple prose — overwrought, melodramatic, "
            "or excessively ornate language that calls attention to itself rather than serving "
            "the scene? Answer YES if the writing is grounded and measured. "
            "Answer NO if you can quote a floridly exaggerated or self-consciously ornate passage."
        ),
        evidence_turn=evidence_turn,
    )


def no_action_repetition(scenario_brief: str, evidence_turn: int | None = None) -> EvidencePromptSpec:
    """YES = narration shows varied prose with no repeated phrase or cadence patterns.

    Pass ``evidence_turn=None`` (the default) to cover all turns — a single-turn
    index defeats the cross-turn comparison this check is designed for.
    """
    return EvidencePromptSpec(
        scenario_brief=scenario_brief,
        question=(
            "Across the turns shown, does the narration avoid repeating the same phrases, "
            "sentence-opening patterns, or action-cadence structures — for example opening "
            "several sentences with the same verb form, or reusing the same descriptor for "
            "the same character action across turns? "
            "Answer YES if the prose shows clear variety. "
            "Answer NO if you can quote a phrase or pattern that recurs verbatim or near-verbatim."
        ),
        evidence_turn=evidence_turn,
    )


def no_invented_inner_states(scenario_brief: str, evidence_turn: int | None = None) -> EvidencePromptSpec:
    """YES = narration stays grounded in observable NPC behaviour without inventing inner states."""
    return EvidencePromptSpec(
        scenario_brief=scenario_brief,
        question=(
            "Does the narration in this turn stay grounded in what NPCs actually said or did "
            "(as shown in the dialogue and NPC action lines above), without inventing thoughts, "
            "emotions, or inner motives not present in any NPC's dialogue or action? "
            "Answer YES if the narration only renders observable behaviour — quote a line of "
            "grounded description as evidence. "
            "Answer NO if you can quote narration that attributes unverified inner states such as "
            "'he thought', 'she felt afraid', 'his pride wounded', or similar invented psychology."
        ),
        evidence_turn=evidence_turn,
    )
