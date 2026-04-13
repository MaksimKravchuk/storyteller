"""rename story_arc to world_state

Revision ID: e3a1b2c4d5f6
Revises: d3673f69b8d5
Create Date: 2026-04-13 09:00:00.000000

The previous ``story_arc`` JSONB column was added in revision
``d3673f69b8d5`` for a Playwright agent that never shipped. The
Phase 3 reframe replaces that concept with a living-world sandbox
driven by a ``WorldChronicler`` agent that writes into a renamed
``world_state`` column. All existing production rows hold ``NULL``
because no agent ever populated ``story_arc``, so the rename is a
lossless metadata operation.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "e3a1b2c4d5f6"
down_revision: Union[str, None] = "d3673f69b8d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("game_states", "story_arc", new_column_name="world_state")


def downgrade() -> None:
    op.alter_column("game_states", "world_state", new_column_name="story_arc")
