"""creator stripe_account_id (Stripe Connect payouts)

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-08-05 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = 'f2a3b4c5d6e7'
down_revision: Union[str, Sequence[str], None] = 'e1f2a3b4c5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'creator',
        sa.Column('stripe_account_id', sqlmodel.sql.sqltypes.AutoString(),
                  nullable=False, server_default=''),
    )


def downgrade() -> None:
    op.drop_column('creator', 'stripe_account_id')
