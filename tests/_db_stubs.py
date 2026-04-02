"""Stub db modules so test imports succeed without a real database."""

import sys
from types import ModuleType
from unittest.mock import MagicMock

_engine_stub = ModuleType("db.engine")
_engine_stub.get_db = MagicMock()  # type: ignore[attr-defined]
sys.modules.setdefault("db.engine", _engine_stub)

_repo_stub = ModuleType("db.repository")
_repo_stub.GameRepository = MagicMock()  # type: ignore[attr-defined]
sys.modules.setdefault("db.repository", _repo_stub)
