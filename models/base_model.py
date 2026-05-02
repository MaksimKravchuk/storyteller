from uuid import uuid4

from pydantic import UUID4
from pydantic import BaseModel as PydanticBaseModel
from pydantic import Field


class StorytellerBase(PydanticBaseModel):
    """Pydantic base for domain models with an auto-generated UUID4.

    The field is a real ``uuid.UUID`` (version 4) rather than a string so that
    every NPC / Scene / Location / Setting identifier is parsed and validated
    at construction. Producers that pass an LLM-emitted ``str`` flow through
    pydantic's coercion path (and are rejected at parse time if invalid) —
    runtime resolvers no longer need to defend against ``npc_uuid="guard"``.
    """

    uuid: UUID4 = Field(default_factory=uuid4)
