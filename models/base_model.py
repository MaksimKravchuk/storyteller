import uuid as uuid_mod
from dataclasses import dataclass, field

from pydantic import BaseModel as PydanticBaseModel
from pydantic import Field


@dataclass(kw_only=True)
class BaseModel:
    """Legacy dataclass base kept for ``GameState``/``PlayerState``.

    Step 4 of the pydantic migration will retire this in favour of
    ``StorytellerBase``. New code must inherit from ``StorytellerBase``.
    """

    uuid: str = field(default_factory=lambda: str(uuid_mod.uuid4()))


class StorytellerBase(PydanticBaseModel):
    """Pydantic base for migrated domain models."""

    uuid: str = Field(default_factory=lambda: str(uuid_mod.uuid4()))
