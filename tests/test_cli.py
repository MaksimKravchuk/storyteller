"""CLI smoke tests using Click's CliRunner."""

from unittest.mock import AsyncMock, patch

from click.testing import CliRunner

from main import main


def _make_mock_engine(opening: str = "You stand in the Roman Forum."):
    engine = AsyncMock()
    engine.start_game.return_value = opening
    engine.process_action.return_value = "The guard blocks your path."
    return engine


def _make_mock_config():
    mock = type(
        "Cfg",
        (),
        {
            "director_model": "test-director",
            "agent_model": "test-agent",
            "narrator_model": "test-narrator",
        },
    )()
    return mock


def _invoke(input_text: str):
    runner = CliRunner()
    with (
        patch("main.load_config", return_value=_make_mock_config()),
        patch("main.create_engine", return_value=_make_mock_engine()),
    ):
        return runner.invoke(main, input=input_text)


def test_banner_and_quit():
    outcome = _invoke("Ancient Rome\nquit\n")

    assert outcome.exit_code == 0
    assert "STORYTELLER" in outcome.output
    assert "Describe your desired setting" in outcome.output
    assert "Thanks for playing!" in outcome.output


def test_opening_narration_displayed():
    outcome = _invoke("Ancient Rome\nquit\n")

    assert outcome.exit_code == 0
    assert "You stand in the Roman Forum." in outcome.output


def test_action_then_quit():
    outcome = _invoke("Ancient Rome\nlook around\nquit\n")

    assert outcome.exit_code == 0
    assert "The guard blocks your path." in outcome.output
    assert "Thanks for playing!" in outcome.output


def test_model_names_in_banner():
    outcome = _invoke("Ancient Rome\nquit\n")

    assert "test-director" in outcome.output
    assert "test-agent" in outcome.output
    assert "test-narrator" in outcome.output
