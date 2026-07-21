"""page published (review-before-live)

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-07-21 15:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, Sequence[str], None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # server_default true → existing (already-live) pages stay published; new
    # generated drafts set published=False explicitly at ingest.
    op.add_column('page', sa.Column('published', sa.Boolean(), nullable=False,
                                    server_default=sa.true()))
    op.create_index(op.f('ix_page_published'), 'page', ['published'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_page_published'), table_name='page')
    op.drop_column('page', 'published')
