"""Captured transcript of a narrative e2e game session.

Decoupled from any LLM client — this module only holds the shape of the
transcript and renders it as plain text for a judge prompt.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TurnRecord:
    """A single player-action -> narration pair from a captured session."""

    index: int  # 1-based turn number
    goal: str  # high-level goal the driver was pursuing
    player_action: str  # the short action text sent to the game
    narration: str  # the game's narrated response


@dataclass(frozen=True)
class SessionTranscript:
    """Full captured session ready to be handed to the narrative judge."""

    setting: str
    opening_narration: str
    turns: tuple[TurnRecord, ...]

    def render_for_judge(self) -> str:
        """Render the transcript as a numbered plain-text block."""
        opening = self.opening_narration.strip()
        blocks: list[str] = [
            f"SETTING: {self.setting}",
            "",
            "OPENING SCENE:",
            opening,
        ]
        for turn in self.turns:
            blocks.append("")
            blocks.append(_format_turn_header(turn))
            _append_turn_body(blocks, turn)
        return "\n".join(blocks)


def _format_turn_header(turn: TurnRecord) -> str:
    idx = turn.index
    goal = turn.goal
    return f"--- Turn {idx} (goal: {goal}) ---"


def _append_turn_body(blocks: list[str], turn: TurnRecord) -> None:
    action = turn.player_action
    narration = turn.narration.strip()
    blocks.append(f"Player: {action}")
    blocks.append("Narration:")
    blocks.append(narration)
