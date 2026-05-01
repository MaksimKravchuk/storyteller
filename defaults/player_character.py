"""Default template character for tests and anonymization.

Surfaced in the web UI via a "Use template" button so a player who
doesn't want to type real personal details can start a game with a
canned, plausible character. Tests import the constant directly so
fixtures stay deterministic.
"""

from __future__ import annotations

from models.player_character_input import PlayerCharacterInput

TEMPLATE_CHARACTER = PlayerCharacterInput(
    name="",
    appearance=(
        "average build, brown hair, wearing dark jeans and a grey hoodie, "
        "with a small messenger bag slung over one shoulder"
    ),
    inventory=["smartphone", "wallet", "keys", "notebook", "pen"],
)
