import uuid as uuid_mod

from pydantic import BaseModel as PydanticBaseModel
from pydantic import Field


class StorytellerBase(PydanticBaseModel):
    """Pydantic base for migrated domain models."""

    uuid: str = Field(default_factory=lambda: str(uuid_mod.uuid4()))
