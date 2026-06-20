"""add emotional charge to knowledge_nodes and values_vector to npcs

Revision ID: d7e8f9a0b1c2
Revises: a1b2c3d4e5f7
Create Date: 2026-06-19 12:00:00.000000

Dwarf-Fortress-style deterministic emotional memory. ``knowledge_nodes``
gains the felt charge of a personal memory — a signed ``valence`` and a
pre-decay ``charge_intensity``, plus a ``charge_category`` keying the
value-axis signature the per-witness deriver reads at read time. ``npcs``
gains a ``values_vector`` (the seven-axis weighting that colours how
strongly an event charges emotion). Existing rows backfill to neutral
(zero charge / empty category / empty vector), so pre-existing memories
and NPCs contribute no emotional signal until new charged events arrive.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "d7e8f9a0b1c2"
down_revision: Union[str, None] = "a1b2c3d4e5f7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "knowledge_nodes",
        sa.Column("valence", sa.Float(), nullable=False, server_default="0.0"),
    )
    op.add_column(
        "knowledge_nodes",
        sa.Column("charge_intensity", sa.Float(), nullable=False, server_default="0.0"),
    )
    op.add_column(
        "knowledge_nodes",
        sa.Column("charge_category", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "npcs",
        sa.Column(
            "values_vector",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("npcs", "values_vector")
    op.drop_column("knowledge_nodes", "charge_category")
    op.drop_column("knowledge_nodes", "charge_intensity")
    op.drop_column("knowledge_nodes", "valence")
