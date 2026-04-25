"""Unit tests for Chronicler-emitted goal drafts and updates."""

from __future__ import annotations

import allure

from cast._chronicler_goals import apply_goal_drafts, apply_goal_updates
from cast.schemas.chronicler_response import GoalDraft, GoalUpdate
from models.goal import Goal, GoalKind, GoalScope, GoalStatus
from models.npc_card import NPCCard


def _make_npc(uuid: str, name: str) -> NPCCard:
    npc = NPCCard(name=name, occupation="x")
    npc.uuid = uuid
    return npc


@allure.epic("World Chronicler")
@allure.feature("Chronicler goal emission")
class TestApplyGoalDrafts:
    """``apply_goal_drafts`` validates UUIDs and refuses to overwrite ACTIVE goals."""

    @allure.story("Goal drafts")
    @allure.title("Valid GoalDraft assigns life_goal on the named NPC")
    def test_valid_draft_assigns_life_goal(self) -> None:
        npcs = {
            "npc-brutus": _make_npc("npc-brutus", "Brutus"),
            "npc-marcus": _make_npc("npc-marcus", "Marcus"),
        }
        draft = GoalDraft(
            npc_uuid="npc-brutus",
            kind=GoalKind.KILL,
            description="Avenge brother by killing Marcus",
            target_uuid="npc-marcus",
            source_thread_uuid="thread-1",
        )

        apply_goal_drafts(npcs, [draft])

        brutus = npcs["npc-brutus"]
        assert brutus.life_goal is not None
        assert brutus.life_goal.scope is GoalScope.LIFE
        assert brutus.life_goal.kind is GoalKind.KILL
        assert brutus.life_goal.target_uuid == "npc-marcus"

    @allure.story("Goal drafts")
    @allure.title("Unknown npc_uuid is skipped without raising")
    def test_unknown_npc_skipped(self) -> None:
        npcs = {"npc-marcus": _make_npc("npc-marcus", "Marcus")}
        draft = GoalDraft(npc_uuid="ghost", kind=GoalKind.KILL, description="x")

        apply_goal_drafts(npcs, [draft])

        assert all(npc.life_goal is None for npc in npcs.values())

    @allure.story("Goal drafts")
    @allure.title("Unknown target_uuid causes the draft to be dropped")
    def test_unknown_target_skipped(self) -> None:
        npcs = {"npc-brutus": _make_npc("npc-brutus", "Brutus")}
        draft = GoalDraft(
            npc_uuid="npc-brutus",
            kind=GoalKind.KILL,
            description="hunt phantom",
            target_uuid="ghost",
        )

        apply_goal_drafts(npcs, [draft])

        assert npcs["npc-brutus"].life_goal is None

    @allure.story("Goal drafts")
    @allure.title("ACTIVE life_goal is not overwritten by a chronicler draft")
    def test_active_life_goal_preserved(self) -> None:
        brutus = _make_npc("npc-brutus", "Brutus")
        brutus.life_goal = Goal(
            kind=GoalKind.KILL,
            description="original vendetta",
            target_uuid="npc-marcus",
        )
        npcs = {
            "npc-brutus": brutus,
            "npc-marcus": _make_npc("npc-marcus", "Marcus"),
        }
        draft = GoalDraft(
            npc_uuid="npc-brutus",
            kind=GoalKind.PURSUE,
            description="chase someone else",
            target_uuid="npc-marcus",
        )

        apply_goal_drafts(npcs, [draft])

        assert brutus.life_goal.description == "original vendetta"  # unchanged

    @allure.story("Goal drafts")
    @allure.title("ABANDONED life_goal CAN be replaced by a fresh draft")
    def test_abandoned_life_goal_replaced(self) -> None:
        brutus = _make_npc("npc-brutus", "Brutus")
        brutus.life_goal = Goal(
            kind=GoalKind.KILL,
            description="old vendetta",
            target_uuid="npc-marcus",
            status=GoalStatus.ABANDONED,
        )
        npcs = {
            "npc-brutus": brutus,
            "npc-marcus": _make_npc("npc-marcus", "Marcus"),
        }
        draft = GoalDraft(
            npc_uuid="npc-brutus",
            kind=GoalKind.PROTECT,
            description="protect Marcus instead",
            target_uuid="npc-marcus",
        )

        apply_goal_drafts(npcs, [draft])

        assert brutus.life_goal.kind is GoalKind.PROTECT


@allure.epic("World Chronicler")
@allure.feature("Chronicler goal emission")
class TestApplyGoalUpdates:
    """``apply_goal_updates`` flips ACTIVE life goals to ABANDONED or BLOCKED."""

    @allure.story("Goal updates")
    @allure.title("ABANDONED update flips ACTIVE life goal and records the reason")
    def test_abandoned_update_applied(self) -> None:
        brutus = _make_npc("npc-brutus", "Brutus")
        brutus.life_goal = Goal(kind=GoalKind.KILL, description="vendetta", target_uuid="npc-marcus")
        npcs = {"npc-brutus": brutus}
        update = GoalUpdate(npc_uuid="npc-brutus", status="abandoned", reason="Marcus left the city")

        apply_goal_updates(npcs, [update])

        assert brutus.life_goal.status is GoalStatus.ABANDONED
        assert any("abandoned" in note for note in brutus.life_goal.progress_notes)

    @allure.story("Goal updates")
    @allure.title("BLOCKED update is applied even without a reason note")
    def test_blocked_update_without_reason(self) -> None:
        brutus = _make_npc("npc-brutus", "Brutus")
        brutus.life_goal = Goal(kind=GoalKind.KILL, description="vendetta")
        npcs = {"npc-brutus": brutus}
        update = GoalUpdate(npc_uuid="npc-brutus", status="blocked")

        apply_goal_updates(npcs, [update])

        assert brutus.life_goal.status is GoalStatus.BLOCKED

    @allure.story("Goal updates")
    @allure.title("Update on NPC with no life_goal is a silent no-op")
    def test_no_life_goal_is_noop(self) -> None:
        brutus = _make_npc("npc-brutus", "Brutus")
        npcs = {"npc-brutus": brutus}
        update = GoalUpdate(npc_uuid="npc-brutus", status="abandoned", reason="reason")

        apply_goal_updates(npcs, [update])

        assert brutus.life_goal is None

    @allure.story("Goal updates")
    @allure.title("Update on already-COMPLETED goal does not regress to ABANDONED")
    def test_completed_goal_not_regressed(self) -> None:
        brutus = _make_npc("npc-brutus", "Brutus")
        brutus.life_goal = Goal(
            kind=GoalKind.KILL,
            description="vendetta",
            status=GoalStatus.COMPLETED,
        )
        npcs = {"npc-brutus": brutus}
        update = GoalUpdate(npc_uuid="npc-brutus", status="abandoned", reason="reason")

        apply_goal_updates(npcs, [update])

        assert brutus.life_goal.status is GoalStatus.COMPLETED  # unchanged
