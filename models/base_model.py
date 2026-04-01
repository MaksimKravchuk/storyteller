import uuid as uuid_mod
from dataclasses import dataclass, field


@dataclass(kw_only=True)
class BaseModel:
    uuid: str = field(default_factory=lambda: str(uuid_mod.uuid4()))
