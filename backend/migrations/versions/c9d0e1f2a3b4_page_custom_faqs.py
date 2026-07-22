"""page custom_faqs (creator-added FAQ entries)

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-07-22 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = 'c9d0e1f2a3b4'
down_revision: Union[str, Sequence[str], None] = 'b8c9d0e1f2a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('page', sa.Column('custom_faqs', sqlmodel.sql.sqltypes.AutoString(),
                                    nullable=False, server_default=''))


def downgrade() -> None:
    op.drop_column('page', 'custom_faqs')
