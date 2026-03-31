"""E2E test: attack NPC combat flow."""

import allure

from tests.e2e.process_io import read_until, send_line
from tests.e2e.conftest import ACTION_TIMEOUT, GAME_START_TIMEOUT, SETTING
from tests.e2e.tester_agent import TesterAgent

_SETTING_PROMPT_TIMEOUT = 15
_MIN_COMBAT_RESPONSE_LEN = 30
_ATTACK_GOAL = (
    "Identify an NPC present in the scene and attack them. Output only the attack command, e.g. 'attack the guard'."
)


@allure.feature("CLI")
@allure.story("Combat")
@allure.severity(allure.severity_level.CRITICAL)
def test_attack_random_npc(game_process):
    agent = TesterAgent()

    with allure.step("Start game"):
        read_until(game_process.stdout, "Describe your desired setting", timeout=_SETTING_PROMPT_TIMEOUT)
        send_line(game_process.stdin, SETTING)
        opening = read_until(game_process.stdout, "\n> ", timeout=GAME_START_TIMEOUT)

    with allure.step("TesterAgent decides attack"):
        attack_action = agent.decide_action(opening, _ATTACK_GOAL)
        allure.attach(attack_action, name="chosen_action", attachment_type=allure.attachment_type.TEXT)

    with allure.step("Send attack action"):
        send_line(game_process.stdin, attack_action)

    with allure.step("Wait for combat narration"):
        combat_response = read_until(game_process.stdout, "\n> ", timeout=ACTION_TIMEOUT)
        allure.attach(combat_response, name="combat_narration", attachment_type=allure.attachment_type.TEXT)
        assert len(combat_response) > _MIN_COMBAT_RESPONSE_LEN

    with allure.step("Verify combat occurred"):
        combat_verified = agent.verify(
            combat_response,
            "a combat or fight occurred, including attacks, a physical confrontation, or a dice roll outcome",
        )
        assert combat_verified
