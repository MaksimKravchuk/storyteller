"""restrict account plan values

Revision ID: e8f9a0b1c2d3
Revises: d7e8f9a0b1c2
Create Date: 2026-06-28 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "e8f9a0b1c2d3"
down_revision: Union[str, None] = "d7e8f9a0b1c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ACCOUNTS = "accounts"
_PLAN_CONSTRAINT = "ck_accounts_plan_allowed"
_FRIEND_BETA = "friend_beta"
_ADMIN = "admin"


def upgrade() -> None:
    """Normalize legacy rows and constrain account plans to known values."""
    op.execute(
        f"UPDATE {_ACCOUNTS} "
        f"SET plan = '{_FRIEND_BETA}' "
        f"WHERE plan IS NULL OR plan NOT IN ('{_FRIEND_BETA}', '{_ADMIN}')",
    )
    op.create_check_constraint(
        _PLAN_CONSTRAINT,
        _ACCOUNTS,
        f"plan IN ('{_FRIEND_BETA}', '{_ADMIN}')",
    )


def downgrade() -> None:
    """Remove the account-plan value constraint."""
    op.drop_constraint(_PLAN_CONSTRAINT, _ACCOUNTS, type_="check")
