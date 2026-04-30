"""Internal helpers for ``interfaces.web.service``.

Split out to keep the public service module under wemake's
``WPS202 too many module members`` cap.
"""

from __future__ import annotations

from dataclasses import dataclass

from config import Config
from db.repository import GameRepository
from engine.factory import create_engine_from_state
from engine.game_engine import GameEngine
from interfaces.web.character import build_character_info
from interfaces.web.schemas import CharacterCreationInput, GameSnapshot
from interfaces.web.transcript import build_transcript

_DEFAULT_LANGUAGE = "English"


@dataclass(frozen=True)
class StartGameParams:
    """Bundle of parameters for ``service.start_game_for_player``."""

    player_id: str
    setting: str
    language: str
    character: CharacterCreationInput | None = None


def snapshot_from_engine(engine: GameEngine, language: str = _DEFAULT_LANGUAGE) -> GameSnapshot:
    """Build a ``GameSnapshot`` view from a fully-initialised engine.

    ``language`` is forwarded to ``build_transcript`` so history lines can
    be re-wrapped with language-appropriate entity lemmatisation.
    """
    game_state, _, _ = engine.assert_running()
    return GameSnapshot(
        game_id=str(game_state.uuid),
        setting=game_state.setting.name,
        transcript=build_transcript(game_state.conversation_log, language),
        turn_count=game_state.turn_count,
        character=build_character_info(game_state),
    )


def session_language(session_row: dict) -> str:
    """Extract a language from a session row, defaulting to English."""
    return session_row.get("language") or _DEFAULT_LANGUAGE


async def restore_engine(
    repo: GameRepository,
    cfg: Config,
    session_row: dict,
) -> GameEngine | None:
    """Load saved state for a session and return a restored engine, or None."""
    loaded = await repo.load_game_state(session_row["id"])
    if loaded is None:
        return None
    game_state, kg, events = loaded
    return await create_engine_from_state(
        cfg,
        game_state,
        kg,
        events,
        language=session_language(session_row),
    )
