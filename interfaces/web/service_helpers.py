"""Internal helpers for ``interfaces.web.service``.

Split out to keep the public service module under wemake's
``WPS202 too many module members`` cap.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from config import Config
from db.repository import GameRepository
from engine.factory import create_engine_from_state
from engine.game_engine import GameEngine
from interfaces.web import character, world
from interfaces.web.errors import GameNotFoundError
from interfaces.web.schemas import CharacterCreationInput, GameSnapshot
from interfaces.web.schemas_library import GameSummary
from interfaces.web.transcript import build_transcript, player_visible_turn_count

_DEFAULT_LANGUAGE = "English"
_DEFAULT_USER_PLAN = "friend_beta"


@dataclass(frozen=True)
class StartGameParams:
    """Bundle of parameters for ``service.start_game_for_player``."""

    player_id: str
    setting: str
    language: str
    plan: str = _DEFAULT_USER_PLAN
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
        turn_count=player_visible_turn_count(game_state.conversation_log),
        character=character.build_character_info(game_state),
        world=world.build_world_view(game_state),
    )


def session_language(session_row: Mapping[str, object]) -> str:
    """Extract a language from a session row, defaulting to English."""
    return str(session_row.get("language") or _DEFAULT_LANGUAGE)


async def owned_session_context(repo: GameRepository, player_id: str, game_id: str) -> tuple[str, str]:
    """Return the owned session id and language or raise a 404-safe error."""
    session_row = await repo.web_games.get_by_game(player_id, game_id)
    if session_row is None:
        raise GameNotFoundError(player_id)
    return str(session_row["id"]), session_language(session_row)


def _turn_count(row: Mapping[str, object]) -> int:
    raw_value = row.get("turn_count")
    return int(raw_value) if isinstance(raw_value, int) else 0


def game_summary_from_row(row: Mapping[str, object]) -> GameSummary:
    """Build a compact library summary from a joined session/game row."""
    setting = str(row.get("setting") or "Untitled setting")
    return GameSummary(
        game_id=str(row["game_id"]),
        title=str(row.get("title") or setting),
        setting=setting,
        turn_count=_turn_count(row),
    )


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
