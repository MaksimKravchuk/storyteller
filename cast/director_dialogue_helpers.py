"""Pure helper functions for dialogue routing."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from loguru import logger

from cast import dice as dice_mod
from cast.schemas.anachronism import NPCAnachronismResult
from knowledge.memory import DialoguePair
from knowledge.memory_slots import MemorySlots
from llm.turn_event_logger import record_turn_event
from models.game_state import GameState

# Re-bind the dice symbols this module reads frequently into local
# names so the surrounding code stays terse without growing the
# top-level import budget past WPS201.
ContestOutcome = dice_mod.ContestOutcome
ContestRoll = dice_mod.ContestRoll
ContestType = dice_mod.ContestType
roll_contest = dice_mod.roll_contest

# Skill discount the anachronism modifier applies to one side of the
# dice contest. Spec (issue #186): the player intimidating an NPC
# with a smartphone discounts the *target's* defence; an NPC trying
# to attack a player wielding magic discounts the *NPC's* offence.
# Half of effective_strangeness so a 10/10 anachronism is at most a
# -5 to a single skill — a meaningful but not unbeatable thumb on
# the scale.
_ANACHRONISM_SKILL_PENALTY_DIVISOR = 2


def role_matched_uuids(targets_lower: set[str], game_state: GameState) -> set[UUID]:
    """Return UUIDs of scene NPCs whose role matches a target name."""
    scene = game_state.current_scene
    if not scene:
        return set()
    matched: set[UUID] = set()
    for snpc in scene.npcs_present:
        if snpc.uuid is not None and snpc.role.lower() in targets_lower:
            matched.add(snpc.uuid)
    return matched


def name_matched_uuids(targets_lower: set[str], game_state: GameState) -> set[UUID]:
    """Return UUIDs of NPCs whose name matches a target."""
    matched: set[UUID] = set()
    for uid, npc in game_state.npcs.items():
        if npc.name.lower() in targets_lower:
            matched.add(uid)
    return matched


def deduplicate_by_name(uuids: set[UUID], game_state: GameState) -> list[UUID]:
    """De-duplicate NPC UUIDs so each name appears only once."""
    seen: set[str] = set()
    unique_uuids: list[UUID] = []
    for uid in uuids:
        npc = game_state.npcs.get(uid)
        if npc and npc.name.lower() not in seen:
            seen.add(npc.name.lower())
            unique_uuids.append(uid)
    return unique_uuids


def resolve_target_uuids(target_names: list[str], game_state: GameState) -> list[UUID]:
    """Resolve target names to a de-duplicated list of NPC UUIDs."""
    targets_lower = {target.lower() for target in target_names}
    matched = role_matched_uuids(targets_lower, game_state) | name_matched_uuids(targets_lower, game_state)
    return deduplicate_by_name(matched, game_state)


def _format_contest_text(
    player_action: str,
    contest_roll: ContestRoll,
    status_hint: str = "",
    perceived_rewrite: str = "",
) -> str:
    """Format action text with dice roll result for prompt injection.

    When *perceived_rewrite* is non-empty, the in-period framing of the
    action is appended as a separate clause so the Actor LLM speaks in
    the witness's voice instead of repeating ``halt, citizen!`` while
    the dice contest already says the NPC is bewildered.
    """
    framing = ""
    if perceived_rewrite:
        framing = "\n\nThe NPC perceives this as: {0}".format(perceived_rewrite)
    return (
        "{0}\n\n"
        "[DICE ROLL: actor {1}+{2} vs "
        "target {3}+{4}]\n"
        "OUTCOME: {5}\n"
        "You MUST narrate this outcome. Do NOT override the dice result.{6}{7}"
    ).format(
        player_action,
        contest_roll.actor_roll,
        contest_roll.actor_bonus,
        contest_roll.target_roll,
        contest_roll.target_bonus,
        contest_roll.description,
        status_hint,
        framing,
    )


def _combat_status_hint(outcome: ContestOutcome) -> str:
    """Return a status-update hint when the target is injured in combat."""
    if outcome in (ContestOutcome.ACTOR_SUCCEEDS, ContestOutcome.ACTOR_DOMINATES):
        return (
            "\nThe NPC is injured. Update their physical status to reflect the injury. "
            "Append [STATUS: <description>] at the end of your response."
        )
    return ""


def _apply_skill_modifiers(
    contest_type: ContestType,
    target_skill: int,
    anachronism: NPCAnachronismResult | None,
) -> tuple[int, int]:
    """Adjust the (actor_skill, target_skill) pair for an anachronism modifier.

    Returns the original pair unchanged when no anachronism applies.
    Otherwise discounts whichever side the spec calls out: a
    ``COMBAT`` NPC reacting to a magic-wielding player loses
    *actor_skill*; every other contest where the player drives
    (intimidation, persuasion, deception, stealth) loses *target*
    skill — i.e. the NPC's defence is easier to overcome when they're
    bewildered.
    """
    if anachronism is None or anachronism.effective_strangeness <= 0:
        return 0, target_skill
    penalty = anachronism.effective_strangeness // _ANACHRONISM_SKILL_PENALTY_DIVISOR
    if contest_type == ContestType.COMBAT:
        return -penalty, target_skill
    return 0, max(0, target_skill - penalty)


@dataclass(frozen=True)
class _RollSetup:
    """Bundled per-call inputs for the contest roll path.

    Bundling ``contest_type`` + ``default_skill`` keeps
    :func:`_roll_and_format` inside the WPS211 argument budget
    without pushing the caller into mid-function branching.
    """

    contest_type: ContestType
    default_skill: int


@dataclass(frozen=True)
class ContestRequest:
    """Per-turn description of *what kind of* contest the dialogue should roll.

    Bundles the two flags that previously lived as separate parameters
    on :func:`build_contested_action` (``is_aggressive`` and
    ``contest_info``) so the public signature stays inside the WPS211
    budget. ``is_aggressive`` takes priority when both are set, matching
    the historical resolution order.
    """

    is_aggressive: bool = False
    contest_info: dict | None = None


def build_contested_action(
    player_action: str,
    npc: Any,
    request: ContestRequest,
    *,
    anachronism: NPCAnachronismResult | None = None,
    rng: random.Random | None = None,
) -> tuple[str, ContestRoll | None]:
    """Build action text and optional contest roll for an NPC interaction.

    Resolution order matches the legacy two-flag form: ``is_aggressive``
    on *request* wins → roll combat; otherwise ``contest_info`` selects
    a typed contest; otherwise the plain action text is returned with
    no roll.

    *anachronism* (when non-None and ``effective_strangeness > 0``)
    discounts one side's skill and threads the
    ``perceived_rewrite`` into the formatted Actor input — see
    :func:`_apply_skill_modifiers` and :func:`_format_contest_text`.
    """
    if request.is_aggressive:
        return _roll_and_format(player_action, npc, _RollSetup(ContestType.COMBAT, 3), anachronism, rng)

    contest_info = request.contest_info
    if contest_info:
        try:
            ctype = ContestType(contest_info.get("type", "combat"))
        except ValueError:
            logger.warning("Unknown contest type {!r}, falling back to COMBAT", contest_info.get("type"))
            ctype = ContestType.COMBAT
        return _roll_and_format(player_action, npc, _RollSetup(ctype, 0), anachronism, rng)

    return player_action, None


def _build_dice_event_payload(
    contest_roll: ContestRoll,
    player_action: str,
    npc: Any,
    anachronism: NPCAnachronismResult | None,
) -> dict[str, Any]:
    """Build the ``dice_contest`` turn-event payload, with optional anachronism telemetry."""
    payload: dict[str, Any] = {
        **dice_mod.contest_roll_to_dict(contest_roll),
        "player_action": player_action,
        "npc_name": getattr(npc, "name", None),
    }
    if anachronism is not None:
        payload["anachronism_strangeness"] = anachronism.effective_strangeness
        payload["anachronism_encounter_count"] = anachronism.encounter_count
        payload["anachronism_concepts"] = list(anachronism.unfamiliar_concepts)
    return payload


def _resolve_contest(
    npc: Any,
    setup: _RollSetup,
    anachronism: NPCAnachronismResult | None,
    rng: random.Random | None,
) -> ContestRoll:
    """Resolve target/actor skills (with anachronism modifier) and roll the contest."""
    _actor_attr, target_attr = dice_mod.CONTEST_SKILL_MAP[setup.contest_type]
    raw_target = npc.get_attribute(target_attr, setup.default_skill)
    actor_skill, target_skill = _apply_skill_modifiers(setup.contest_type, raw_target, anachronism)
    return roll_contest(setup.contest_type, actor_skill, target_skill, _rng=rng)


def _roll_and_format(
    player_action: str,
    npc: Any,
    setup: _RollSetup,
    anachronism: NPCAnachronismResult | None,
    rng: random.Random | None,
) -> tuple[str, ContestRoll]:
    """Roll a contest and format the action text with the result."""
    contest_roll = _resolve_contest(npc, setup, anachronism, rng)
    status_hint = _combat_status_hint(contest_roll.outcome) if setup.contest_type == ContestType.COMBAT else ""
    record_turn_event(
        "dice_contest",
        _build_dice_event_payload(contest_roll, player_action, npc, anachronism),
        npc_id=getattr(npc, "uuid", None),
    )
    perceived_rewrite = anachronism.perceived_rewrite if anachronism else ""
    return (
        _format_contest_text(player_action, contest_roll, status_hint, perceived_rewrite),
        contest_roll,
    )


def format_dialogue_summary_pairs(
    work_items: list[Any],
    dialogue_entries: list[dict[str, Any]],
    player_action: str,
    player_name: str,
) -> list[DialoguePair]:
    """Build ``(npc_id, log, slots)`` :data:`DialoguePair`s for the memory summariser.

    Each pair carries the NPC id, the raw transcript, and structured
    slots (subject = NPC name, object = player name, action = ``said``).
    The slots are deterministic from the speaker/listener pair so the
    memory summariser only needs to generate the free-text summary.
    """
    return [
        (
            work_item[0].uuid,
            "Player: {0}\n{1}: {2}".format(
                player_action,
                work_item[0].name,
                entry.get("response", ""),
            ),
            MemorySlots(subject=work_item[0].name, object=player_name, action="said"),
        )
        for work_item, entry in zip(work_items, dialogue_entries)
    ]


_ROLE_USER = "user"
_ROLE_ASSISTANT = "assistant"


def append_conversation_history(
    work_items: list[Any],
    dialogue_entries: list[dict[str, Any]],
    player_action: str,
) -> None:
    """Append the bare player utterance + NPC reply to each NPC's persisted log.

    Bare ``player_action`` is used (not the contest-wrapped ``action_text``
    seen by the Actor LLM) so the persisted history matches the
    role/content shape the benchmark fixture and the JSONB column expect.
    """
    for work_item, entry in zip(work_items, dialogue_entries):
        npc = work_item[0]
        npc.conversation_history.append({"role": _ROLE_USER, "content": player_action})
        npc.conversation_history.append({"role": _ROLE_ASSISTANT, "content": entry.get("response", "")})
