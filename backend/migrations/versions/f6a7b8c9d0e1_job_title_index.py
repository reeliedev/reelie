"""generationjob title + status index

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-07-21 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, Sequence[str], None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('generationjob', sa.Column('title', sqlmodel.sql.sqltypes.AutoString(),
                                             nullable=False, server_default=''))
    op.create_index(op.f('ix_generationjob_status'), 'generationjob', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_generationjob_status'), table_name='generationjob')
    op.drop_column('generationjob', 'title')
