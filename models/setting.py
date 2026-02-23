from __future__ import annotations

from models.base_model import BaseModel


class Setting(BaseModel):
    """Structured historical / geographical context produced by the Data Miner.

    Represents the researched backdrop of the game world.
    """

    def __init__(
        self,
        *,
        name: str,
        time_period: str,
        region: str,
        summary: str,
        key_persons: list[dict[str, str]] | None = None,
        key_events: list[dict[str, str]] | None = None,
        locations: list[dict[str, str]] | None = None,
        traditions: list[str] | None = None,
        technologies: list[str] | None = None,
        social_structure: str = "",
        raw_sources: list[str] | None = None,
    ):
        super().__init__()
        self.name = name
        self.time_period = time_period
        self.region = region
        self.summary = summary
        self.key_persons: list[dict[str, str]] = key_persons or []
        self.key_events: list[dict[str, str]] = key_events or []
        self.locations: list[dict[str, str]] = locations or []
        self.traditions: list[str] = traditions or []
        self.technologies: list[str] = technologies or []
        self.social_structure = social_structure
        self.raw_sources: list[str] = raw_sources or []
