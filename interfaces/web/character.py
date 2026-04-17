"""Builder for the web API's ``CharacterInfo`` payload.

Projects the player-facing fields of ``GameState`` into the stable
``CharacterInfo`` DTO exposed on both ``GameSnapshot`` and
``ActionResponse``. Kept in its own module so the service layer stays
thin and the shape of the Character sidebar lives next to the schemas.
"""

from __future__ import annotations

from typing import cast

from knowledge.node import KnowledgeNode
from models.game_state import GameState

from interfaces.web.character_schemas import CharacterInfo, FactSource, KnownNPC, RememberedFact


def _known_npcs(game_state: GameState) -> list[KnownNPC]:
    """Project each introduced NPC (by UUID) into a ``KnownNPC`` row.

    Iterates ``player.known_npcs`` in sorted UUID order so the payload
    is stable across requests — ``known_npcs`` is a ``set`` and
    :mod:`db.converters.player` persists it sorted, so readers already
    expect a deterministic projection. Skips UUIDs that no longer
    resolve to a card — cards can be evicted by the NPC ticker between
    turns while still appearing in ``player.known_npcs``.
    """
    rows: list[KnownNPC] = []
    for npc_uuid in sorted(game_state.player.known_npcs):
        npc = game_state.npcs.get(npc_uuid)
        if npc is None:
            continue
        rows.append(
            KnownNPC(
                name=npc.name,
                occupation=npc.occupation,
                descriptor=npc.short_descriptor,
            ),
        )
    return rows


def _fact_from_node(node: KnowledgeNode) -> RememberedFact:
    """Build a ``RememberedFact`` from a ``KnowledgeNode``.

    The cast narrows the enum name to the ``FactSource`` ``Literal`` so
    pydantic validation stays type-safe; every ``KnowledgeSource`` enum
    member's ``name`` matches one of the four allowed values.
    """
    source_name = cast(FactSource, node.source.name)
    return RememberedFact(text=node.text, source=source_name)


def _learned_facts(game_state: GameState) -> list[RememberedFact]:
    """Project each remembered fact UUID into a ``RememberedFact`` row.

    Iterates ``player.learned_facts`` in sorted UUID order for the same
    stability reason as ``_known_npcs``. Skips UUIDs that no longer
    resolve to a graph node — the graph can drop nodes during
    memory-preservation sweeps while their UUID is still listed in
    ``player.learned_facts``.
    """
    graph = game_state.knowledge_graph
    rows: list[RememberedFact] = []
    for fact_uuid in sorted(game_state.player.learned_facts):
        node = graph.get_node(fact_uuid)
        if node is None:
            continue
        rows.append(_fact_from_node(node))
    return rows


def build_character_info(game_state: GameState) -> CharacterInfo:
    """Build the ``CharacterInfo`` payload for the given game state."""
    player = game_state.player
    return CharacterInfo(
        name=player.name,
        appearance=player.appearance,
        physical_status=player.physical_status,
        inventory=list(player.inventory),
        known_npcs=_known_npcs(game_state),
        recent_events=list(player.player_event_log),
        learned_facts=_learned_facts(game_state),
    )
