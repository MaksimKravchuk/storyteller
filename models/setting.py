from __future__ import annotations

from dataclasses import dataclass, field

from models.base_model import BaseModel


@dataclass(kw_only=True)
class Setting(BaseModel):
    """Structured historical / geographical context produced by the Data Miner.

    Represents the researched backdrop of the game world.
    """

    name: str
    time_period: str
    region: str
    summary: str
    key_persons: list[dict[str, str]] = field(default_factory=list)
    key_events: list[dict[str, str]] = field(default_factory=list)
    locations: list[dict[str, str]] = field(default_factory=list)
    traditions: list[str] = field(default_factory=list)
    technologies: list[str] = field(default_factory=list)
    social_structure: str = ""
    raw_sources: list[str] = field(default_factory=list)
