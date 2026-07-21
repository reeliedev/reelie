"""generationjob phase + preview + duration (live analysis UI)

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-07-22 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = 'b8c9d0e1f2a3'
down_revision: Union[str, Sequence[str], None] = 'a7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('generationjob', sa.Column('phase', sqlmodel.sql.sqltypes.AutoString(),
                                             nullable=False, server_default=''))
    op.add_column('generationjob', sa.Column('preview', sqlmodel.sql.sqltypes.AutoString(),
                                             nullable=False, server_default=''))
    op.add_column('generationjob', sa.Column('duration_s', sa.Float(),
                                             nullable=False, server_default='0'))


def downgrade() -> None:
    op.drop_column('generationjob', 'duration_s')
    op.drop_column('generationjob', 'preview')
    op.drop_column('generationjob', 'phase')
