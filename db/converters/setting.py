"""Setting ↔ DB row converters."""

from __future__ import annotations

from db.converters._columns import COL_GAME_STATE_ID, COL_ID, COL_NAME
from models.setting import Setting


def setting_to_row(setting: Setting, game_state_id: str) -> dict:
    return {
        COL_ID: setting.uuid,
        COL_GAME_STATE_ID: game_state_id,
        COL_NAME: setting.name,
        "time_period": setting.time_period,
        "region": setting.region,
        "summary": setting.summary,
        "key_persons": setting.key_persons,
        "key_events": setting.key_events,
        "locations_data": setting.locations,
        "traditions": setting.traditions,
        "technologies": setting.technologies,
        "social_structure": setting.social_structure,
        "raw_sources": setting.raw_sources,
    }


def row_to_setting(row) -> Setting:
    setting = Setting(
        name=row[COL_NAME],
        time_period=row["time_period"],
        region=row["region"],
        summary=row["summary"],
        key_persons=row["key_persons"],
        key_events=row["key_events"],
        locations=row["locations_data"],
        traditions=row["traditions"],
        technologies=row["technologies"],
        social_structure=row["social_structure"],
        raw_sources=row["raw_sources"],
    )
    setting.uuid = row[COL_ID]
    return setting
