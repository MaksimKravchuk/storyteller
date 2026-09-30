"""Build and store the library playbill for a freshly started story.

The playbill is a deterministic projection of the post-prologue
``GameState`` (like :mod:`interfaces.web.world`): no LLM call, so every
story gets a poster for free. Cast names route through
``build_world_view`` and therefore ``NPCCard.label_for_player``.
"""

from __future__ import annotations

import re

from db.repository import GameRepository
from interfaces.web.schemas_library import Playbill, PlaybillCastMember
from interfaces.web.world import build_world_view
from interfaces.web.world_schemas import ScenePerson
from models.game_state import GameState, PlayerState

_TAGLINE_MAX_CHARS = 160
_CAST_LIMIT = 4
_GENERIC_PLACE_TYPE = "generic"
_MARKUP_RE = re.compile(r"[*_`]")
_SENTENCE_END_RE = re.compile(r"(?<=[.!?…])\s")
_TRAILING_PUNCTUATION = ",;:—– "
# The engine's name for a player who left the name blank; not billed as the hero.
_ANONYMOUS_HERO = PlayerState.model_fields["name"].default


def _opening_text(game_state: GameState) -> str:
    for entry in game_state.conversation_log:
        response = entry.get("response")
        if response:
            return str(response)
    return ""


def tagline_from_opening(opening: str) -> str:
    """Return the opening's first sentence as plain text, clipped to poster length."""
    plain = " ".join(_MARKUP_RE.sub("", opening).split())
    first_sentence = _SENTENCE_END_RE.split(plain, maxsplit=1)[0]
    if len(first_sentence) <= _TAGLINE_MAX_CHARS:
        return first_sentence
    clipped = first_sentence[:_TAGLINE_MAX_CHARS].rsplit(" ", 1)[0]
    return "{0}…".format(clipped.rstrip(_TRAILING_PUNCTUATION))


def _billed_hero(name: str) -> str | None:
    return None if name == _ANONYMOUS_HERO else name


def _cast(people: list[ScenePerson]) -> list[PlaybillCastMember]:
    billed = people[:_CAST_LIMIT]
    return [PlaybillCastMember(label=person.label, known=person.known) for person in billed]


def build_playbill(game_state: GameState) -> Playbill:
    """Project the story's poster copy from current game state."""
    world = build_world_view(game_state)
    current = world.map.current
    setting = game_state.setting
    return Playbill(
        tagline=tagline_from_opening(_opening_text(game_state)),
        setting=setting.name,
        hero=_billed_hero(game_state.player.name),
        hero_look=game_state.player.appearance,
        era=setting.time_period,
        region=setting.region,
        place=current.name if current else None,
        place_type=current.location_type if current else _GENERIC_PLACE_TYPE,
        daypart=world.clock.time_of_day,
        cast=_cast(world.people),
    )


async def save_playbill(repo: GameRepository, session_id: str, game_state: GameState) -> None:
    """Store the playbill for a new story."""
    await repo.web_games.posters.save_playbill(session_id, build_playbill(game_state).model_dump())
