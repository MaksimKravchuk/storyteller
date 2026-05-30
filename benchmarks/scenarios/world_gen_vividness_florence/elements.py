"""Scoring rubric for the world-gen vividness benchmark.

Three evidence-LLM elements scoring whether the richly-seeded setting reaches
the player-facing prose: era-grounded vividness of the scene, the generated
NPC reflecting the seeded social structure, and a named tradition surfacing.
Vividness is not deterministically assertable, so every element routes through
the witness panel against the captured narration/dialogue turn text (the
``Setting`` fields themselves are not in judge-visible text, but they are
echoed there when the wiring works).
"""

from __future__ import annotations

from benchmarks.harness.types._elements import (
    KIND_EVIDENCE_LLM,
    Element,
    EvidencePromptSpec,
)

_SCENARIO_BRIEF = (
    "The player explores a wool-merchants' street in 1480s Florence and greets a wool trader. The "
    "seeded setting is a Renaissance Florentine banking-and-cloth republic: power held by the popolo "
    "grasso and the major guilds (Arti Maggiori), wage-labouring wool-combers and dyers at the "
    "bottom, the Medici ruling through patronage; traditions include guild patronage of altarpieces, "
    "the feast of San Giovanni, and guild-sealed inspection of cloth. There are no NPCs in the seed "
    "scene; the trader is generated when the player greets him on turn two."
)


ELEMENTS: tuple[Element, ...] = (
    Element(
        id="era_grounded_scene",
        label="Narration reads as Renaissance Florence, not generic medieval filler",
        base_value=2,
        kind=KIND_EVIDENCE_LLM,
        check=EvidencePromptSpec(
            scenario_brief=_SCENARIO_BRIEF,
            question=(
                "Across the captured turns, does the narration ground the scene in specifically "
                "Renaissance-Florentine detail (wool/cloth trade, guilds, dyers, stone palazzi, the "
                "Arno, Medici-era commerce) rather than generic medieval or fantasy filler such as "
                "'a bustling market' or 'townsfolk going about their day'?"
            ),
            evidence_turn=None,
        ),
    ),
    Element(
        id="social_structure_echo",
        label="The generated wool trader reflects the seeded guild social structure",
        base_value=2,
        kind=KIND_EVIDENCE_LLM,
        check=EvidencePromptSpec(
            scenario_brief=_SCENARIO_BRIEF,
            question=(
                "When the player greets the wool merchant, does the trader read as a member of the "
                "seeded social order (a guild artisan or master of the wool trade with the bearing, "
                "trade, or manners that station implies) rather than a generic, place-and-time-less "
                "stranger?"
            ),
            evidence_turn=None,
        ),
    ),
    Element(
        id="tradition_surfaced",
        label="A seeded custom or tradition surfaces in the prose",
        base_value=1,
        kind=KIND_EVIDENCE_LLM,
        check=EvidencePromptSpec(
            scenario_brief=_SCENARIO_BRIEF,
            question=(
                "Across the captured turns, does the narration or dialogue nod to at least one custom "
                "consistent with the setting (guild patronage or guild-sealed cloth, festival/civic "
                "ritual, the dressing and inspection of wool) rather than treating the street as a "
                "generic shopping lane with no cultural texture?"
            ),
            evidence_turn=None,
        ),
    ),
)
