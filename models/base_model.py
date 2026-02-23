import uuid

class BaseModel:
    def __init__(self):
        self.uuid: str = self._generate_uuid()

    def _generate_uuid(self) -> str:
        return str(uuid.uuid4())