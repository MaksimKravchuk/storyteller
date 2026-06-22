"""Situated-agenda detection for NPC autonomous turns.

When an NPC shares a scene with someone they have a standing hostile or
supportive intent toward — encoded either as a signed
:class:`~models.relationship.Relationship` or as an intent-flavoured
knowledge fact mentioning that NPC by name — the autonomous-turn prompt
lifts the baseline "most turns are routine" nudge and appends a
situated agenda so the LLM can choose in character whether to act on the
moment.

Routine NPCs (peaceful relationships, neutral knowledge) fall
through every gate here and see the unchanged baseline prompt.
"""

from __future__ import annotations

from uuid import UUID

from cast import npc_agenda_helpers as _agenda
from models.game_state import GameState
from models.npc_card import NPCCard
from models.relationship import Relationship, RelationshipKind
from models.scene import Scene

KNOWLEDGE_VIOLENCE_KEYWORDS: frozenset[str] = frozenset(("kill", "murder", "harm", "wound"))

_OPPORTUNITY_TEMPLATE = (
    "OPPORTUNITY: {target} — the target of your standing hostile intent — "
    "is right here, right now. Every turn you wait is a turn you let this "
    "moment slip. Decide what THIS character, in THIS mood, with THIS "
    "equipment would do: ATTACK directly, approach under STEALTH first, "
    "or IDLE only if there is a concrete obstacle (witnesses, lack of "
    "weapon, personal code) that makes acting right now impossible. "
    "Name that obstacle in your action description if you choose to wait."
)

TACTICAL_HOSTILE_CLAUSE = (
    "TACTICAL CHOICE: You have a hostile goal. Pick your approach deliberately:\n"
    "  STEALTH — close in unseen; use this when your target is not watching you.\n"
    "  MOVE    — reposition to a better angle or closer range before committing.\n"
    "  ATTACK  — direct strike; use this only when you have a clear opening.\n"
    "Commit to one action. Do not hedge."
)

_KNOWLEDGE_VIOLENCE_RE = _agenda.keyword_regex(KNOWLEDGE_VIOLENCE_KEYWORDS)


def get_opportunity_clause(npc: NPCCard, game_state: GameState) -> str | None:
    """Return a hostile OPPORTUNITY clause naming the target, or None."""
    clause = get_agenda_clause(npc, game_state)
    if clause is None or not is_hostile_agenda_clause(clause):
        return None
    return clause


def get_agenda_clause(npc: NPCCard, game_state: GameState) -> str | None:
    """Return a directive OPPORTUNITY clause naming the hostile target, or None.

    When a co-located target is found — via hostile relationship,
    violent knowledge fact, supportive relationship, or supportive
    knowledge fact — the returned string names that target and
    instructs the Actor LLM to choose a concrete action with a named
    obstacle if it waits. Returns ``None`` when no gate fires.
    """
    scene = game_state.current_scene
    if scene is None:
        return None
    co_located = _co_located_npc_uuids(scene, npc)
    if not co_located:
        return None
    target_name = _name_from_relationship(npc, co_located, game_state) or _agenda.name_from_knowledge(
        npc,
        co_located,
        game_state,
        _KNOWLEDGE_VIOLENCE_RE,
    )
    if target_name is None:
        return _agenda.supportive_agenda_from_relationship(
            npc,
            co_located,
            game_state,
        ) or _agenda.supportive_agenda_from_knowledge(npc, co_located, game_state)
    return _OPPORTUNITY_TEMPLATE.format(target=target_name)


def is_hostile_agenda_clause(clause: str) -> bool:
    """Return True when *clause* is the combat-oriented opportunity clause."""
    return clause.startswith("OPPORTUNITY:")


def _co_located_npc_uuids(scene: Scene, self_npc: NPCCard) -> list[UUID]:
    uuids: list[UUID] = []
    for snpc in scene.npcs_present:
        if snpc.uuid is not None and snpc.uuid != self_npc.uuid:
            uuids.append(snpc.uuid)
    return uuids


def _resolve_hostile_target(
    rel: Relationship,
    co_located_set: set[str],
    game_state: GameState,
) -> str | None:
    if rel.kind != RelationshipKind.ENEMY or rel.intensity > -2:
        return None
    return _agenda.relationship_target_name(rel, co_located_set, game_state)


def _name_from_relationship(
    npc: NPCCard,
    co_located_uuids: list[UUID],
    game_state: GameState,
) -> str | None:
    co_located_set = {str(uid) for uid in co_located_uuids}
    for rel in npc.relationships:
        name = _resolve_hostile_target(rel, co_located_set, game_state)
        if name is not None:
            return name
    return None
