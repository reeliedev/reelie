"""page like (guest likes on routines)

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-20 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'pagelike',
        sa.Column('id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('handle', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('slug', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('client_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('handle', 'slug', 'client_id', name='uq_like'),
    )
    op.create_index(op.f('ix_pagelike_handle'), 'pagelike', ['handle'], unique=False)
    op.create_index(op.f('ix_pagelike_slug'), 'pagelike', ['slug'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_pagelike_slug'), table_name='pagelike')
    op.drop_index(op.f('ix_pagelike_handle'), table_name='pagelike')
    op.drop_table('pagelike')
