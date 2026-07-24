"""report (user-reported content — UGC moderation)

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-07-24 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, Sequence[str], None] = 'd0e1f2a3b4c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'report',
        sa.Column('id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('kind', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('ref', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('reason', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('detail', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('reporter_client', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('reporter_user', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('handled', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_report_kind'), 'report', ['kind'], unique=False)
    op.create_index(op.f('ix_report_ref'), 'report', ['ref'], unique=False)
    op.create_index(op.f('ix_report_handled'), 'report', ['handled'], unique=False)
    op.create_index(op.f('ix_report_created_at'), 'report', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_report_created_at'), table_name='report')
    op.drop_index(op.f('ix_report_handled'), table_name='report')
    op.drop_index(op.f('ix_report_ref'), table_name='report')
    op.drop_index(op.f('ix_report_kind'), table_name='report')
    op.drop_table('report')
