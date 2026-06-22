"""Unit tests for the Goal model and its NPCCard wiring."""

from __future__ import annotations

import allure
import pytest

from models.goal import Goal, GoalKind, GoalScope, GoalStatus
from models.npc_card import NPCCard
from tests._uuid_helpers import make_uuid

_MARCUS = make_uuid("npc-marcus")

# Append-only guard: the historical kinds keep their order/values so old
# JSONB rows (which store the string value) stay valid. New kinds are
# appended after these.
_LEGACY_KIND_ORDER: tuple[tuple[str, str], ...] = (
    ("KILL", "kill"),
    ("PURSUE", "pursue"),
    ("ACQUIRE", "acquire"),
    ("PROTECT", "protect"),
    ("FLEE", "flee"),
    ("DEFEND", "defend"),
    ("EAT", "eat"),
    ("ERRAND", "errand"),
    ("REST", "rest"),
    ("FLEE_SCENE", "flee_scene"),
)

_NEW_KIND_VALUES: tuple[tuple[GoalKind, str], ...] = (
    (GoalKind.BEFRIEND, "befriend"),
    (GoalKind.COURT, "court"),
    (GoalKind.GOSSIP, "gossip"),
    (GoalKind.TRADE, "trade"),
    (GoalKind.HELP, "help"),
    (GoalKind.WARN, "warn"),
    (GoalKind.ASK, "ask"),
    (GoalKind.AVOID, "avoid"),
)


def _kill_marcus_goal(last_attempted_action: str | None = None) -> Goal:
    """Build a baseline life-tier KILL goal targeting Marcus, with optional last-action."""
    return Goal(
        kind=GoalKind.KILL,
        description="Avenge brother by killing Marcus",
        target_uuid=_MARCUS,
        last_attempted_action=last_attempted_action,
    )


@allure.epic("NPC Interaction")
@allure.feature("NPC autonomous goals")
class TestGoalKindVocabulary:
    """The GoalKind enum exposes the social/standing kinds without disturbing legacy values."""

    @allure.story("Vocabulary")
    @allure.title("The eight new kinds expose stable lowercase string values")
    @pytest.mark.parametrize(("kind", "value"), _NEW_KIND_VALUES)
    def test_new_kind_values(self, kind: GoalKind, value: str) -> None:
        assert kind.value == value

    @allure.story("Vocabulary")
    @allure.title("Legacy kinds keep their order and values (append-only growth)")
    def test_legacy_kinds_unchanged_and_first(self) -> None:
        first_ten = tuple((member.name, member.value) for member in list(GoalKind)[:10])
        assert first_ten == _LEGACY_KIND_ORDER

    @allure.story("Vocabulary")
    @allure.title("REST already exists and is not redefined by the new vocabulary")
    def test_rest_is_not_new(self) -> None:
        assert GoalKind.REST.value == "rest"
        assert GoalKind.REST not in {kind for kind, _ in _NEW_KIND_VALUES}

    @allure.story("Persistence")
    @allure.title("A Goal carrying any new kind round-trips through JSON")
    @pytest.mark.parametrize("kind", [kind for kind, _ in _NEW_KIND_VALUES])
    def test_new_kind_round_trips_through_json(self, kind: GoalKind) -> None:
        goal = Goal(kind=kind, description="standing agenda", target_uuid=_MARCUS)

        revived = Goal.model_validate_json(goal.model_dump_json())

        assert revived.kind is kind

    @allure.story("Persistence")
    @allure.title("A legacy kind stored as a bare string still validates (old DB rows load)")
    def test_legacy_kind_string_validates(self) -> None:
        revived = Goal.model_validate(
            {"kind": "kill", "description": "avenge", "target_uuid": str(_MARCUS)},
        )

        assert revived.kind is GoalKind.KILL


@allure.epic("NPC Interaction")
@allure.feature("NPC autonomous goals")
class TestGoalModel:
    """Persistent NPC intentions carry across turns and round-trip through JSON."""

    @allure.story("NPCCard default state")
    @allure.title("NPCCard.life_goal and tactical_goal both default to None")
    def test_npc_card_default_goal_is_none(self) -> None:
        npc = NPCCard(name="Anon", occupation="merchant")
        assert npc.life_goal is None
        assert npc.tactical_goal is None

    @allure.story("Two-tier scope")
    @allure.title("Goal.scope defaults to LIFE; tactical scope round-trips through JSON")
    def test_goal_scope_defaults_to_life(self) -> None:
        life_goal = _kill_marcus_goal()
        tactical = Goal(scope=GoalScope.TACTICAL, kind=GoalKind.DEFEND, description="hit back")

        assert life_goal.scope is GoalScope.LIFE
        assert tactical.scope is GoalScope.TACTICAL
        revived = Goal.model_validate_json(tactical.model_dump_json())
        assert revived.scope is GoalScope.TACTICAL
        assert revived.kind is GoalKind.DEFEND

    @allure.story("Persistence")
    @allure.title("Goal preserves every field through pydantic JSON dump and reparse")
    def test_goal_round_trips_through_json(self) -> None:
        goal = _kill_marcus_goal(last_attempted_action="STEALTH")
        goal.record_progress("approached the table")

        revived = Goal.model_validate_json(goal.model_dump_json())

        assert revived.scope is GoalScope.LIFE
        assert revived.kind is GoalKind.KILL
        assert revived.description == "Avenge brother by killing Marcus"
        assert revived.target_uuid == _MARCUS
        assert revived.status is GoalStatus.ACTIVE
        assert revived.last_attempted_action == "STEALTH"
        assert revived.progress_notes == ["approached the table"]

    @allure.story("Bounded progress notes")
    @allure.title("record_progress drops the oldest entry once the budget is exceeded")
    def test_record_progress_caps_notes(self) -> None:
        goal = _kill_marcus_goal()
        for index in range(20):
            goal.record_progress("step {0}".format(index))

        assert len(goal.progress_notes) == 6
        assert goal.progress_notes[0] == "step 14"
        assert goal.progress_notes[-1] == "step 19"

    @allure.story("NPCCard goal carrier")
    @allure.title("NPCCard exposes the seeded Goal on its life_goal field")
    def test_npc_card_carries_a_goal(self) -> None:
        npc = NPCCard(
            name="Brutus",
            occupation="former legionary",
            life_goal=_kill_marcus_goal(),
        )

        assert npc.life_goal is not None
        assert npc.life_goal.kind is GoalKind.KILL
        assert npc.life_goal.target_uuid == _MARCUS
