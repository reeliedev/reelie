"""sale.external_id (AWIN transaction id for idempotent conversion import)

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-08-05 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = 'e2f3a4b5c6d7'
down_revision: Union[str, Sequence[str], None] = 'd1e2f3a4b5c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'sale',
        sa.Column('external_id', sqlmodel.sql.sqltypes.AutoString(),
                  nullable=False, server_default=''),
    )
    op.create_index('ix_sale_external_id', 'sale', ['external_id'])


def downgrade() -> None:
    op.drop_index('ix_sale_external_id', table_name='sale')
    op.drop_column('sale', 'external_id')
