"""creator closed-beta application fields

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-07-20 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('creator', sa.Column('status', sqlmodel.sql.sqltypes.AutoString(),
                                       nullable=False, server_default='pending'))
    op.add_column('creator', sa.Column('instagram', sqlmodel.sql.sqltypes.AutoString(),
                                       nullable=False, server_default=''))
    op.add_column('creator', sa.Column('youtube', sqlmodel.sql.sqltypes.AutoString(),
                                       nullable=False, server_default=''))
    op.add_column('creator', sa.Column('applied_at', sa.DateTime(),
                                       nullable=False, server_default=sa.func.now()))
    op.add_column('creator', sa.Column('reviewed_at', sa.DateTime(), nullable=True))
    op.create_index(op.f('ix_creator_status'), 'creator', ['status'], unique=False)
    # existing creators (seed / already onboarded) are grandfathered in as approved
    op.execute("UPDATE creator SET status='approved'")


def downgrade() -> None:
    op.drop_index(op.f('ix_creator_status'), table_name='creator')
    op.drop_column('creator', 'reviewed_at')
    op.drop_column('creator', 'applied_at')
    op.drop_column('creator', 'youtube')
    op.drop_column('creator', 'instagram')
    op.drop_column('creator', 'status')
