from __future__ import annotations

from models.base_model import StorytellerBase


class Setting(StorytellerBase):
    """Structured historical / geographical context produced by the Data Miner.

    Represents the researched backdrop of the game world.
    """

    name: str
    time_period: str
    region: str
    summary: str
    key_persons: list[dict[str, str]] = []
    key_events: list[dict[str, str]] = []
    locations: list[dict[str, str]] = []
    traditions: list[str] = []
    technologies: list[str] = []
    social_structure: str = ""
