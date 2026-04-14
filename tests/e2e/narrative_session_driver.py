"""Drive an end-to-end game session and capture it as a transcript.

Used by ``test_narrative_quality`` — extracted into its own module so the
test file stays under WPS module-member limits.
"""

import allure

from tests.e2e.conftest import (
    ACTION_TIMEOUT,
    GAME_START_TIMEOUT,
    SETTING,
    assert_process_alive,
)
from tests.e2e.process_io import read_until, send_line
from tests.e2e.session_transcript import SessionTranscript, TurnRecord
from tests.e2e.tester_agent import TesterAgent

_SETTING_PROMPT_TIMEOUT = 15
_TURN_INDEX_WIDTH = 2

TURN_GOALS: tuple[str, ...] = (
    "Explore the starting area and observe details about your surroundings.",
    "Approach and start talking to any visible NPC in the scene.",
    "Ask the NPC about recent local events or notable history.",
    "Travel to a new nearby location mentioned in the narration.",
    "Investigate something suspicious or curious in the current scene.",
    "Wait and observe what happens around you for a moment.",
    "Attempt a risky or confrontational action against an NPC present.",
    "Return to the location where you first started.",
    "Seek out the earlier NPC again and reference what they told you.",
    "Take a decisive closing action that resolves the current situation.",
)


def play_session(game_process) -> SessionTranscript:
    """Start the game, walk through ``TURN_GOALS``, return the transcript."""
    tester = TesterAgent()
    opening = _start_game(game_process)
    turns = _run_turns(game_process, tester, opening)
    return SessionTranscript(
        setting=SETTING,
        opening_narration=opening,
        turns=turns,
    )


def _start_game(game_process) -> str:
    banner = read_until(
        game_process.stdout,
        "Describe your desired setting",
        timeout=_SETTING_PROMPT_TIMEOUT,
    )
    assert_process_alive(game_process)
    allure.attach(banner, name="banner", attachment_type=allure.attachment_type.TEXT)
    send_line(game_process.stdin, SETTING)
    opening = read_until(game_process.stdout, "\n> ", timeout=GAME_START_TIMEOUT)
    assert_process_alive(game_process)
    allure.attach(
        opening,
        name="opening-narration",
        attachment_type=allure.attachment_type.TEXT,
    )
    return opening


def _run_turns(
    game_process,
    tester: TesterAgent,
    opening: str,
) -> tuple[TurnRecord, ...]:
    turns: list[TurnRecord] = []
    last_narration = opening
    for index, goal in enumerate(TURN_GOALS, start=1):
        record = _play_one_turn(game_process, tester, last_narration, index, goal)
        turns.append(record)
        last_narration = record.narration
    return tuple(turns)


def _play_one_turn(
    game_process,
    tester: TesterAgent,
    prev_narration: str,
    index: int,
    goal: str,
) -> TurnRecord:
    action = tester.decide_action(prev_narration, goal)
    send_line(game_process.stdin, action)
    narration = read_until(game_process.stdout, "\n> ", timeout=ACTION_TIMEOUT)
    assert_process_alive(game_process)
    _attach_turn(index, goal, action, narration)
    return TurnRecord(
        index=index,
        goal=goal,
        player_action=action,
        narration=narration,
    )


def _attach_turn(index: int, goal: str, action: str, narration: str) -> None:
    body = "\n".join(
        [
            f"GOAL: {goal}",
            f"ACTION: {action}",
            "",
            narration,
        ],
    )
    padded_index = str(index).zfill(_TURN_INDEX_WIDTH)
    name = f"turn-{padded_index}"
    allure.attach(body, name=name, attachment_type=allure.attachment_type.TEXT)
