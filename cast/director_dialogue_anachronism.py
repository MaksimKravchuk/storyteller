"""Anachronism handling for player dialogue: perceived rewrite + NPC encounter memory."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from cast import _reliability_metrics as reliability_metrics
from cast.schemas.anachronism import AnachronismAssessment
from knowledge import salience as salience_presets
from knowledge.memory import MemoryEvent
from knowledge.memory_slots import MemorySlots
from knowledge.node import KnowledgeScope
from models.game_state import GameState

logger = logging.getLogger(__name__)

# Scores below this read as ordinary speech: no rewrite, no encounter memory.
STRANGENESS_THRESHOLD = 3


async def assess(classifier: Any | None, game_state: GameState, player_action: str) -> AnachronismAssessment | None:
    """Classify ``player_action``; ``None`` when unwired, not strange enough, or the call failed."""
    if classifier is None:
        return None
    try:
        assessment: AnachronismAssessment = await classifier.act(
            player_action,
            {"game_state": game_state, "origin_era": game_state.player.origin_era},
        )
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Anachronism classifier raised unexpectedly; treating the action as ordinary")
        reliability_metrics.record_fallback("director", "anachronism_classify")
        return None
    return assessment if assessment.strangeness_score >= STRANGENESS_THRESHOLD else None


def perceived_action(assessment: AnachronismAssessment | None, player_action: str) -> str:
    """Return how the NPCs perceive ``player_action`` (the original when nothing to rewrite)."""
    if assessment is None:
        return player_action
    return assessment.perceived_rewrite or player_action


async def record_encounter(
    memory_manager: Any,
    game_state: GameState,
    assessment: AnachronismAssessment | None,
    player_action: str,
    npc_uuids: list[Any],
) -> None:
    """Give each addressed NPC a memory of the out-of-era encounter, tagged by concept."""
    if assessment is None or not npc_uuids:
        return
    scene = game_state.current_scene
    await memory_manager.create_memory_from_event(
        MemoryEvent(
            event_description=perceived_action(assessment, player_action),
            witness_ids=npc_uuids,
            scope=KnowledgeScope.LOCAL,
            location_id=scene.location_id if scene else None,
            game_time=game_state.game_clock,
            salience=salience_presets.ANACHRONISM_ENCOUNTER,
            slots=MemorySlots(subject=game_state.player.name, action="said"),
            subject_id=game_state.player.uuid,
            tags=list(assessment.unfamiliar_concepts),
        ),
    )
