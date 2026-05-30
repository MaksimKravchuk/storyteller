"""Runtime helpers for web game start and turn persistence."""

from __future__ import annotations

from dataclasses import dataclass

from db.repository import GameRepository
from engine.game_engine import GameEngine
from engine.session_ops import persist_engine_state
from interfaces.web.character import build_character_info
from interfaces.web.errors import GameStartUnavailableError, is_provider_auth_error
from interfaces.web.schemas import ActionResponse
from interfaces.web.transcript import player_visible_turn_count, render_narrator_html
from interfaces.web.world import build_world_view
from models.player_character_input import PlayerCharacterInput


@dataclass(frozen=True)
class StartPersistence:
    """Inputs needed to start and persist a new web game."""

    repo: GameRepository
    session_id: str
    user_id: str
    engine: GameEngine
    setting: str
    character: PlayerCharacterInput | None

    async def run(self) -> None:
        """Run ``start_game`` and persist the resulting state."""
        await self.engine.start_game(self.setting, character=self.character)
        await persist_engine_state(
            self.repo,
            self.session_id,
            self.engine,
            turn_number=None,
            user_id=self.user_id,
        )


@dataclass(frozen=True)
class ActionPersistence:
    """Inputs needed to process and persist a web player turn."""

    repo: GameRepository
    session_id: str
    engine: GameEngine
    action: str
    language: str
    user_id: str | None = None

    async def run(self) -> ActionResponse:
        """Run a player action through the engine and persist the new state."""
        narration = await self._process_action()
        game_state, _, _ = self.engine.assert_running()
        await persist_engine_state(
            self.repo,
            self.session_id,
            self.engine,
            turn_number=game_state.turn_count,
            user_id=self.user_id,
        )
        await self.repo.commit()
        return ActionResponse(
            narration=narration,
            narration_html=render_narrator_html(
                narration,
                list(game_state.last_visible_entities),
                self.language,
            ),
            turn_count=player_visible_turn_count(game_state.conversation_log),
            character=build_character_info(game_state),
            world=build_world_view(game_state),
        )

    async def _process_action(self) -> str:
        """Process an action and normalize provider auth failures."""
        try:
            return await self.engine.process_action(self.action)
        except Exception as exc:
            if is_provider_auth_error(exc):
                raise GameStartUnavailableError("LLM provider credentials rejected player action") from exc
            raise
