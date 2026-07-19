"""product clip_url + clip_poster

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-19 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('product', sa.Column('clip_url', sqlmodel.sql.sqltypes.AutoString(),
                                       nullable=False, server_default=''))
    op.add_column('product', sa.Column('clip_poster', sqlmodel.sql.sqltypes.AutoString(),
                                       nullable=False, server_default=''))


def downgrade() -> None:
    op.drop_column('product', 'clip_poster')
    op.drop_column('product', 'clip_url')
