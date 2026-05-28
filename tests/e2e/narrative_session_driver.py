"""Drive a live engine session and capture it as a transcript."""

from __future__ import annotations

import allure
import pytest
from engine.game_engine import GameEngine

from config import Config, get_api_key_for_provider, load_config, resolve_model_config
from engine.factory import create_engine
from tests.e2e.session_transcript import SessionTranscript, TurnRecord

SETTING = "Ancient Rome, 1st century AD"

_TURN_SCRIPT: tuple[tuple[str, str], ...] = (
    (
        "Explore the starting area and observe details about your surroundings.",
        "look around carefully and note exits, people, and anything unusual",
    ),
    (
        "Approach and start talking to any visible NPC in the scene.",
        "approach the most visible person and greet them politely",
    ),
    (
        "Ask the NPC about recent local events or notable history.",
        "ask what has happened nearby recently and what people are worried about",
    ),
    (
        "Travel to a new nearby location mentioned in the narration.",
        "go to the nearest place that sounds important or busy",
    ),
    (
        "Investigate something suspicious or curious in the current scene.",
        "inspect the most suspicious detail here and ask nearby people about it",
    ),
    (
        "Wait and observe what happens around you for a moment.",
        "wait quietly and watch what changes around me",
    ),
    (
        "Attempt a risky or confrontational action against an NPC present.",
        "accuse the most suspicious person of hiding the truth",
    ),
    (
        "Return to the location where you first started.",
        "return to where this story began",
    ),
    (
        "Seek out the earlier NPC again and reference what they told you.",
        "find the person I spoke with earlier and mention their warning",
    ),
    (
        "Take a decisive closing action that resolves the current situation.",
        "make a decisive choice based on what I learned and act on it",
    ),
)


async def play_session() -> SessionTranscript:
    """Start a live engine session, play scripted turns, and return the transcript."""
    cfg = load_config()
    _skip_without_required_keys(cfg)
    engine = create_engine(cfg)
    opening = await engine.start_game(SETTING)
    allure.attach(opening, name="opening-narration", attachment_type=allure.attachment_type.TEXT)
    turns = await _play_scripted_turns(engine)
    return SessionTranscript(setting=SETTING, opening_narration=opening, turns=tuple(turns))


async def _play_scripted_turns(engine: GameEngine) -> list[TurnRecord]:
    turns: list[TurnRecord] = []
    index = 0
    while index < len(_TURN_SCRIPT):
        turn_number = index + 1
        goal, action = _TURN_SCRIPT[index]
        turns.append(await _play_one_turn(engine, turn_number, goal, action))
        index += 1
    return turns


async def _play_one_turn(engine: GameEngine, index: int, goal: str, action: str) -> TurnRecord:
    narration = await engine.process_action(action)
    _attach_turn(index, goal, action, narration)
    return TurnRecord(index=index, goal=goal, player_action=action, narration=narration)


def _skip_without_required_keys(cfg: Config) -> None:
    model_ids = [cfg.director_model, cfg.agent_model, cfg.narrator_model]
    if cfg.dramaturge_enabled:
        model_ids.append(cfg.dramaturge_model)
    missing = []
    for model_id in model_ids:
        model_config = resolve_model_config(model_id)
        if not get_api_key_for_provider(model_config.provider, cfg):
            missing.append(model_config.provider.upper())
    if missing:
        names = ", ".join(sorted({_api_key_name(provider) for provider in missing}))
        pytest.skip(f"Missing API key(s) for live narrative session: {names}")


def _api_key_name(provider: str) -> str:
    return "{0}_API_KEY".format(provider)


def _attach_turn(index: int, goal: str, action: str, narration: str) -> None:
    body = "\n".join([f"GOAL: {goal}", f"ACTION: {action}", "", narration])
    allure.attach(body, name=_turn_attachment_name(index), attachment_type=allure.attachment_type.TEXT)


def _turn_attachment_name(index: int) -> str:
    return "turn-{0}".format(str(index).zfill(2))
