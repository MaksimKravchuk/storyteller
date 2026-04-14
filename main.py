"""Storyteller — AI-powered text quest engine.

Simple CLI entry-point for testing the engine.
"""

from __future__ import annotations

import asyncio
import os

import click
from loguru import logger

from config import load_config
from engine.factory import create_engine
from formatting.markdown_render import render
from formatting.platform import ClientPlatform
from log_scrubbing import install_scrubber

_SEPARATOR = "=" * 60
_QUIT_COMMANDS = frozenset(("quit", "exit", "q"))
_LOG_FILE_ENV = "STORYTELLER_LOG_FILE"
_FILE_LOG_FORMAT = "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name} | {message}"


def _configure_logging() -> None:
    """Install the secret scrubber and, when requested, a file sink.

    The scrubber patches every loguru record so no API key or bearer
    token can reach a downstream sink. When ``STORYTELLER_LOG_FILE`` is
    set — as the e2e test harness does when running the CLI as a
    subprocess — an additional plain-text file sink is registered at
    ``INFO`` level so CI can upload the log as an artifact. DEBUG is
    avoided deliberately: httpx / provider SDKs log request headers at
    that level and those may still contain authorization material.

    The default stderr sink installed by loguru on import is left in
    place; this function only ever appends additional sinks.
    """
    install_scrubber()
    log_file = os.environ.get(_LOG_FILE_ENV)
    if not log_file:
        return
    logger.add(
        log_file,
        level="INFO",
        format=_FILE_LOG_FORMAT,
        enqueue=True,
        backtrace=False,
        diagnose=False,
    )


def _print_banner(cfg) -> None:
    click.echo(_SEPARATOR)
    click.echo("  STORYTELLER — AI Text Quest Engine")
    click.echo(_SEPARATOR)
    click.echo(f"  Director: {cfg.director_model}")
    click.echo(f"  Agents:   {cfg.agent_model}")
    click.echo(f"  Narrator: {cfg.narrator_model}")
    click.echo(_SEPARATOR)
    click.echo()


async def _run_game() -> None:
    cfg = load_config()
    engine = create_engine(cfg)
    _print_banner(cfg)

    setting = click.prompt("Describe your desired setting (e.g. 'Rome, 1st century AD')")
    click.echo("\nResearching setting and generating opening scene...\n")
    click.echo(render(await engine.start_game(setting), ClientPlatform.PLAIN))

    while True:
        click.echo("\n> ", nl=False)
        action = click.get_text_stream("stdin").readline().strip()
        if not action:
            continue
        if action.lower() in _QUIT_COMMANDS:
            click.echo("Thanks for playing!")
            break
        response = await engine.process_action(action)
        click.echo("\n{0}".format(render(response, ClientPlatform.PLAIN)))


@click.command()
def main() -> None:
    """Launch the Storyteller text quest engine."""
    _configure_logging()
    asyncio.run(_run_game())


if __name__ == "__main__":
    main()
