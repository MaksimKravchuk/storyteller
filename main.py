"""Storyteller — AI-powered text quest engine.

Simple CLI entry-point for testing the engine.
"""

from __future__ import annotations

import asyncio

import click

from config import load_config
from engine.factory import create_engine
from formatting.markdown_render import render
from formatting.platform import ClientPlatform

_SEPARATOR = "=" * 60
_QUIT_COMMANDS = frozenset(("quit", "exit", "q"))


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
    asyncio.run(_run_game())


if __name__ == "__main__":
    main()
