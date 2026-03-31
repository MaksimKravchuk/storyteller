"""E2E test: game startup flow."""

import allure

from tests.e2e.process_io import read_until, send_line
from tests.e2e.conftest import GAME_START_TIMEOUT, SETTING
from tests.e2e.tester_agent import TesterAgent

_SETTING_PROMPT_TIMEOUT = 15
_MIN_NARRATION_LEN = 50


@allure.feature("CLI")
@allure.story("Game Start")
def test_game_start(game_process):
    agent = TesterAgent()

    with allure.step("Wait for setting prompt"):
        banner = read_until(game_process.stdout, "Describe your desired setting", timeout=_SETTING_PROMPT_TIMEOUT)
        allure.attach(banner, name="banner", attachment_type=allure.attachment_type.TEXT)
        assert "STORYTELLER" in banner

    with allure.step("Send setting"):
        send_line(game_process.stdin, SETTING)

    with allure.step("Wait for opening narration"):
        opening = read_until(game_process.stdout, "\n> ", timeout=GAME_START_TIMEOUT)
        allure.attach(opening, name="opening_narration", attachment_type=allure.attachment_type.TEXT)
        assert len(opening) > _MIN_NARRATION_LEN

    with allure.step("Verify via TesterAgent"):
        scene_verified = agent.verify(opening, "the game has started and an opening scene has been described")
        assert scene_verified
