"""pageview (page-load analytics incl. AI crawlers)

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-07-23 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = 'd0e1f2a3b4c5'
down_revision: Union[str, Sequence[str], None] = 'c9d0e1f2a3b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'pageview',
        sa.Column('id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('handle', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('page_slug', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('kind', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('agent', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('session', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('referer', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('ts', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_pageview_handle'), 'pageview', ['handle'], unique=False)
    op.create_index(op.f('ix_pageview_page_slug'), 'pageview', ['page_slug'], unique=False)
    op.create_index(op.f('ix_pageview_kind'), 'pageview', ['kind'], unique=False)
    op.create_index(op.f('ix_pageview_agent'), 'pageview', ['agent'], unique=False)
    op.create_index(op.f('ix_pageview_ts'), 'pageview', ['ts'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_pageview_ts'), table_name='pageview')
    op.drop_index(op.f('ix_pageview_agent'), table_name='pageview')
    op.drop_index(op.f('ix_pageview_kind'), table_name='pageview')
    op.drop_index(op.f('ix_pageview_page_slug'), table_name='pageview')
    op.drop_index(op.f('ix_pageview_handle'), table_name='pageview')
    op.drop_table('pageview')
