"""Stable identifiers for the NPC-autonomy murder plot scenario.

Also re-exports :class:`uuid.UUID` so :mod:`state` can import the type
alongside these identifiers and stay under WPS's import-count cap.
"""

from __future__ import annotations

from uuid import UUID

from benchmarks._uuid_helpers import make_uuid

BRUTUS_UUID: UUID = make_uuid("npc-brutus-legionary")
BRUTUS_NAME = "Brutus"
BRUTUS_OCCUPATION = "former legionary"

MARCUS_UUID: UUID = make_uuid("npc-marcus-merchant")
MARCUS_NAME = "Marcus"
MARCUS_OCCUPATION = "cloth merchant"
