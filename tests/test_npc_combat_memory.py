"""Unit tests for ``cast._npc_combat_memory._format_combat_event``.

The combat-memory text seeds witness recall: it must include the
resolution (who won, severity, lethality), not only the inciting verb,
or co-located NPCs end up "knowing the fight started" but unable to
recall how it ended.
"""

from __future__ import annotations

import allure

from cast._npc_combat_memory import CombatEvent, _format_combat_event
from cast._npc_outcome import OutcomeKind
from models.npc_card import NPCCard


def _pair() -> tuple[NPCCard, NPCCard]:
    return NPCCard(name="Brutus", occupation="legionary"), NPCCard(name="Marcus", occupation="merchant")


@allure.epic("Memory & Persistence")
@allure.feature("Autonomous combat memory")
class TestFormatCombatEvent:
    """``_format_combat_event`` renders resolution-aware witness memory text."""

    @allure.story("Lethal physical clash")
    @allure.title("Lethal physical attack reads as a killing blow with the lethality flag")
    def test_lethal_physical_attack_reads_as_killing_blow(self) -> None:
        actor, target = _pair()
        text = _format_combat_event(
            CombatEvent(actor=actor, target=target, new_value="dead", kind=OutcomeKind.PHYSICAL),
        )

        assert "Brutus" in text
        assert "Marcus" in text
        assert "attacked" in text
        assert "killed" in text
        assert "lethal" in text
        assert "dead" in text

    @allure.story("Non-lethal physical clash")
    @allure.title("Non-lethal physical attack reads as a wounding hit, not a kill")
    def test_non_lethal_physical_attack_reads_as_wounding_hit(self) -> None:
        actor, target = _pair()
        text = _format_combat_event(
            CombatEvent(actor=actor, target=target, new_value="wounded", kind=OutcomeKind.PHYSICAL),
        )

        assert "Brutus" in text
        assert "Marcus" in text
        assert "attacked" in text
        assert "wounded" in text
        assert "non-lethal" in text
        assert "killed" not in text

    @allure.story("Intimidation clash")
    @allure.title("Intimidation outcome reads as cowing the target without lethality")
    def test_intimidation_reads_as_cowing_outcome(self) -> None:
        actor, target = _pair()
        text = _format_combat_event(
            CombatEvent(actor=actor, target=target, new_value="frightened", kind=OutcomeKind.MOOD),
        )

        assert "Brutus" in text
        assert "Marcus" in text
        assert "intimidated" in text
        assert "frightened" in text
        assert "killed" not in text
        assert "wounded" not in text
