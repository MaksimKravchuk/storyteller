"""Schemas for the Data Miner LLM JSON responses."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator

# Fields that the original ``cast/data_miner.py`` code coerces with ``... or []``
# because the LLM sometimes returns JSON ``null`` for empty collections.
_NULLABLE_LIST_FIELDS = (
    "key_persons",
    "key_events",
    "locations",
    "traditions",
    "technologies",
)


class SettingPerson(BaseModel):
    """Historical person the Data Miner surfaces for the setting."""

    name: str = ""
    role: str = ""
    description: str = ""


class SettingEvent(BaseModel):
    """Historical event the Data Miner surfaces for the setting."""

    name: str = ""
    date: str = ""
    description: str = ""


class SettingLocation(BaseModel):
    """Notable place the Data Miner surfaces for the setting."""

    name: str = ""
    type: str = ""
    description: str = ""


class SearchTermsResponse(BaseModel):
    """Typed view of the Data Miner search-term extraction response."""

    search_terms: list[str] = Field(default_factory=list)


class SettingResponse(BaseModel):
    """Typed view of the Data Miner synthesised-setting response.

    The three nested lists use typed sub-models rather than
    ``list[dict[str, str]]`` so the emitted JSON Schema has concrete
    ``properties`` on every object node — without that, OpenAI strict
    mode rejects the schema because free-form-dict objects carry
    ``additionalProperties: {...}`` instead of ``false``.
    """

    name: str = "Unknown"
    time_period: str = ""
    region: str = ""
    summary: str = ""
    key_persons: list[SettingPerson] = Field(default_factory=list)
    key_events: list[SettingEvent] = Field(default_factory=list)
    locations: list[SettingLocation] = Field(default_factory=list)
    traditions: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    social_structure: str = ""

    @field_validator(*_NULLABLE_LIST_FIELDS, mode="before")
    @classmethod
    def _none_to_empty(cls, raw_value: Any) -> Any:
        """Coerce JSON ``null`` into an empty list for the list-valued fields."""
        if raw_value is None:
            return []
        return raw_value
