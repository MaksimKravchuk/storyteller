"""Per-NPC dedup helpers used by the Narrator.

Two Director paths can emit a dialogue entry for the same NPC on one
turn (primary response + retaliation summary); ``npc_turns`` is
similarly vulnerable when downstream code merges multiple NPC
schedulers. Serialising the duplicates produces an ``and then… and
then…`` cadence in the rendered prose, so we collapse the lists
per-NPC before they reach the narration prompt.

Order of first appearance is preserved, exact duplicate texts are
dropped, and distinct texts for the same NPC are joined with
``_MULTI_RESPONSE_SEP`` so the Narrator sees a single bullet per
character.
"""

from __future__ import annotations

from cast.schemas.turn_outputs import DialogueEntry, NPCTurnEntry

_MULTI_RESPONSE_SEP = " / "


def _join_distinct(bucket: list[str]) -> str:
    return _MULTI_RESPONSE_SEP.join(bucket)


def _merged_dialogue(existing: DialogueEntry, incoming: DialogueEntry, bucket: list[str]) -> DialogueEntry:
    return DialogueEntry(
        npc_name=incoming.npc_name,
        response=_join_distinct(bucket),
        contest_roll=existing.contest_roll or incoming.contest_roll,
    )


def _merged_npc_turn(existing: NPCTurnEntry, incoming: NPCTurnEntry, bucket: list[str]) -> NPCTurnEntry:
    return NPCTurnEntry(
        npc_name=incoming.npc_name,
        action=_join_distinct(bucket),
        action_type=existing.action_type,
    )


def dedup_dialogue(entries: list[DialogueEntry]) -> list[DialogueEntry]:
    """Collapse same-NPC dialogue entries into one per name."""
    grouped: dict[str, DialogueEntry] = {}
    seen: dict[str, list[str]] = {}
    for entry in entries:
        bucket = seen.setdefault(entry.npc_name, [])
        if entry.response in bucket:
            continue
        bucket.append(entry.response)
        existing = grouped.get(entry.npc_name)
        if existing is None:
            grouped[entry.npc_name] = entry
            continue
        grouped[entry.npc_name] = _merged_dialogue(existing, entry, bucket)
    return list(grouped.values())


def dedup_npc_turns(entries: list[NPCTurnEntry]) -> list[NPCTurnEntry]:
    """Collapse same-NPC ``npc_turns`` entries, mirroring dialogue dedup."""
    grouped: dict[str, NPCTurnEntry] = {}
    seen: dict[str, list[str]] = {}
    for entry in entries:
        bucket = seen.setdefault(entry.npc_name, [])
        if entry.action in bucket:
            continue
        bucket.append(entry.action)
        existing = grouped.get(entry.npc_name)
        if existing is None:
            grouped[entry.npc_name] = entry
            continue
        grouped[entry.npc_name] = _merged_npc_turn(existing, entry, bucket)
    return list(grouped.values())
