"""Turn joined library rows into ``GameSummary`` cards."""

from __future__ import annotations

from typing import Mapping

from loguru import logger
from pydantic import ValidationError

from interfaces.web.schemas_library import GameSummary, Playbill


def _turn_count(row: Mapping[str, object]) -> int:
    raw_value = row.get("turn_count")
    return int(raw_value) if isinstance(raw_value, int) else 0


def _playbill(row: Mapping[str, object]) -> Playbill | None:
    raw_playbill = row.get("playbill")
    if not isinstance(raw_playbill, dict):
        return None
    try:
        return Playbill.model_validate(raw_playbill)
    except ValidationError:
        logger.warning("Library row {0} has an unreadable playbill; showing the plain card", row.get("game_id"))
        return None


def game_summary_from_row(row: Mapping[str, object]) -> GameSummary:
    """Build a compact library summary from a joined session/game/poster row."""
    setting = str(row.get("setting") or "Untitled setting")
    return GameSummary(
        game_id=str(row["game_id"]),
        title=str(row.get("title") or setting),
        setting=setting,
        turn_count=_turn_count(row),
        playbill=_playbill(row),
        has_poster_image=bool(row.get("has_poster_image")),
    )
