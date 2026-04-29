"""GameEvent ↔ DB row converters."""

from __future__ import annotations

from db.converters._columns import COL_GAME_STATE_ID, COL_ID, COL_LOCATION_ID, COL_NAME, COL_SCOPE
from timeline.event import EventEffect, EventStatus, GameEvent


def game_event_to_row(event: GameEvent, game_state_id: str) -> dict:
    return {
        COL_ID: event.uuid,
        COL_GAME_STATE_ID: game_state_id,
        COL_NAME: event.name,
        "scheduled_at": event.scheduled_at,
        "duration": event.duration,
        "completes_at": event.completes_at,
        "status": event.status.value,
        "owner_id": event.owner_id,
        COL_LOCATION_ID: event.location_id,
        COL_SCOPE: event.scope,
        "effects": [
            {
                "effect_type": eff.effect_type,
                "target_id": eff.target_id,
                "effect_data": eff.effect_data,
            }
            for eff in event.effects
        ],
        "on_complete_description": event.on_complete_description,
    }


def row_to_game_event(row) -> GameEvent:
    return GameEvent(
        uuid=row[COL_ID],
        name=row[COL_NAME],
        scheduled_at=row["scheduled_at"],
        duration=row["duration"],
        owner_id=row["owner_id"],
        location_id=row[COL_LOCATION_ID],
        scope=row[COL_SCOPE],
        effects=[
            EventEffect(
                effect_type=eff["effect_type"],
                target_id=eff["target_id"],
                effect_data=eff.get("effect_data", eff.get("params", {})),
            )
            for eff in row["effects"]
        ],
        on_complete_description=row["on_complete_description"],
        completes_at=row["completes_at"],
        status=EventStatus(row["status"]),
    )
