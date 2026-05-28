"""Transcript shape for end-to-end narrative quality evaluation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TurnRecord:
    """One player action and resulting narration from a live session."""

    index: int
    goal: str
    player_action: str
    narration: str


@dataclass(frozen=True)
class SessionTranscript:
    """Full play transcript consumed by the narrative judge."""

    setting: str
    opening_narration: str
    turns: tuple[TurnRecord, ...]

    def render(self) -> str:
        """Render the transcript as plain text for an LLM judge prompt."""
        sections = [
            f"SETTING: {self.setting}",
            "",
            "OPENING:",
            self.opening_narration.strip(),
        ]
        for turn in self.turns:
            sections.extend(
                [
                    "",
                    f"TURN {turn.index}: {turn.goal}",
                    f"PLAYER: {turn.player_action}",
                    "NARRATION:",
                    turn.narration.strip(),
                ],
            )
        return "\n".join(sections)
