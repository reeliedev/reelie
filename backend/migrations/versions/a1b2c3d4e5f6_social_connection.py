"""social connection (OAuth: YouTube / Instagram)

Revision ID: a1b2c3d4e5f6
Revises: d9ff1b149d91
Create Date: 2026-07-19 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'd9ff1b149d91'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'socialconnection',
        sa.Column('id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('user_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('platform', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('external_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('username', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('access_token', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('refresh_token', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('token_expires_at', sa.DateTime(), nullable=True),
        sa.Column('scopes', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('connected_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'platform', name='uq_conn_user_platform'),
    )
    op.create_index(op.f('ix_socialconnection_user_id'), 'socialconnection', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_socialconnection_user_id'), table_name='socialconnection')
    op.drop_table('socialconnection')
