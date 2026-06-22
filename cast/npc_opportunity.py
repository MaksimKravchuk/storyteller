"""Opportunity-window detection for NPC autonomous turns.

When an NPC shares a scene with someone they have a standing intent
toward, the autonomous-turn prompt lifts the baseline "most turns are
routine" nudge and appends an OPPORTUNITY clause so the LLM can choose
in character whether to act on the moment. Two flavours are detected:

* a *hostile* opportunity — a hostile :class:`~models.relationship.Relationship`
  or a violence-flavoured knowledge fact naming the co-located NPC — which
  also appends the combat-only :data:`TACTICAL_HOSTILE_CLAUSE`;
* a *positive* opportunity — a FRIEND/ALLY/KIN relationship or a
  help/trade/warn-flavoured knowledge fact — which invites a non-violent
  social action and never carries the combat coaching.

Hostile wins precedence: when both could fire, the hostile clause is
returned unchanged so the combat path is never softened. Routine NPCs
(neutral relationships, neutral knowledge) fall through every gate here
and see the unchanged baseline prompt. The matching primitives live in
:mod:`cast._opportunity_detection`; this module only orchestrates them.
"""

from __future__ import annotations

from typing import NamedTuple
from uuid import UUID

from cast._opportunity_detection import (
    KNOWLEDGE_KEYWORD_RE,
    POSITIVE_KEYWORD_RE,
    POSITIVE_RELATIONSHIP_KINDS,
    TargetResolver,
    co_located_npc_uuids,
    name_from_knowledge,
    resolve_named_target,
)
from models.game_state import GameState
from models.npc_card import NPCCard
from models.relationship import Relationship, RelationshipKind

_OPPORTUNITY_TEMPLATE = (
    "OPPORTUNITY: {target} — the target of your standing hostile intent — "
    "is right here, right now. Every turn you wait is a turn you let this "
    "moment slip. Decide what THIS character, in THIS mood, with THIS "
    "equipment would do: ATTACK directly, approach under STEALTH first, "
    "or IDLE only if there is a concrete obstacle (witnesses, lack of "
    "weapon, personal code) that makes acting right now impossible. "
    "Name that obstacle in your action description if you choose to wait."
)

_POSITIVE_OPPORTUNITY_TEMPLATE = (
    "OPPORTUNITY: {target} — someone you hold a standing positive bond or "
    "intent toward — is right here, right now. This is a chance to act on "
    "it in character: approach them, offer help, propose a trade, share "
    "news, or warn them of a danger — whatever THIS character, in THIS "
    "mood, would do. Pursue the connection through words and gestures, "
    "never force. IDLE only if something concrete makes reaching out "
    "impossible right now."
)

TACTICAL_HOSTILE_CLAUSE = (
    "TACTICAL CHOICE: You have a hostile goal. Pick your approach deliberately:\n"
    "  STEALTH — close in unseen; use this when your target is not watching you.\n"
    "  MOVE    — reposition to a better angle or closer range before committing.\n"
    "  ATTACK  — direct strike; use this only when you have a clear opening.\n"
    "Commit to one action. Do not hedge."
)


class OpportunityClause(NamedTuple):
    """A resolved opportunity directive plus whether it is hostile.

    ``is_hostile`` gates the combat-only :data:`TACTICAL_HOSTILE_CLAUSE`
    follow-up in the turn prompt — a positive (ally) opportunity must not
    inherit the STEALTH/ATTACK coaching.
    """

    text: str
    is_hostile: bool


def get_opportunity_clause(npc: NPCCard, game_state: GameState) -> OpportunityClause | None:
    """Return an OPPORTUNITY directive naming a co-located target, or None.

    A hostile co-located target (relationship or violent knowledge fact)
    yields a hostile clause and takes precedence. Failing that, a positive
    co-located target (FRIEND/ALLY/KIN relationship or positive-intent
    knowledge fact) yields a non-violent clause. Returns ``None`` when no
    gate fires (routine turn).
    """
    scene = game_state.current_scene
    if scene is None:
        return None
    co_located = co_located_npc_uuids(scene, npc)
    if not co_located:
        return None
    hostile = _name_from_relationship(npc, co_located, game_state, _resolve_hostile_target) or name_from_knowledge(
        npc, co_located, game_state, KNOWLEDGE_KEYWORD_RE
    )
    if hostile is not None:
        return OpportunityClause(_OPPORTUNITY_TEMPLATE.format(target=hostile), is_hostile=True)
    positive = _name_from_relationship(npc, co_located, game_state, _resolve_positive_target) or name_from_knowledge(
        npc, co_located, game_state, POSITIVE_KEYWORD_RE
    )
    if positive is not None:
        return OpportunityClause(_POSITIVE_OPPORTUNITY_TEMPLATE.format(target=positive), is_hostile=False)
    return None


def _resolve_hostile_target(rel: Relationship, co_located_set: set[str], game_state: GameState) -> str | None:
    if rel.kind != RelationshipKind.ENEMY or rel.intensity > -2:
        return None
    return resolve_named_target(rel, co_located_set, game_state)


def _resolve_positive_target(rel: Relationship, co_located_set: set[str], game_state: GameState) -> str | None:
    if rel.kind not in POSITIVE_RELATIONSHIP_KINDS or rel.intensity < 2:
        return None
    return resolve_named_target(rel, co_located_set, game_state)


def _name_from_relationship(
    npc: NPCCard,
    co_located_uuids: list[UUID],
    game_state: GameState,
    resolve: TargetResolver,
) -> str | None:
    co_located_set = {str(uid) for uid in co_located_uuids}
    for rel in npc.relationships:
        name = resolve(rel, co_located_set, game_state)
        if name is not None:
            return name
    return None
