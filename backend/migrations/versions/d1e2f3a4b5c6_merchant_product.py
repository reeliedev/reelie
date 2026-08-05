"""merchant_product (AWIN feed catalogue for direct deep links)

Revision ID: d1e2f3a4b5c6
Revises: f2a3b4c5d6e7
Create Date: 2026-08-05 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


revision: str = 'd1e2f3a4b5c6'
down_revision: Union[str, Sequence[str], None] = 'f2a3b4c5d6e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'merchantproduct',
        sa.Column('id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('merchant_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default=''),
        sa.Column('merchant_name', sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default=''),
        sa.Column('brand', sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default=''),
        sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default=''),
        sa.Column('name_norm', sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default=''),
        sa.Column('ean', sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default=''),
        sa.Column('upc', sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default=''),
        sa.Column('deep_link', sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default=''),
        sa.Column('product_url', sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default=''),
        sa.Column('image', sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default=''),
        sa.Column('price', sa.Float(), nullable=False, server_default='0'),
        sa.Column('currency', sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default=''),
        sa.Column('in_stock', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_merchantproduct_merchant_id', 'merchantproduct', ['merchant_id'])
    op.create_index('ix_merchantproduct_name_norm', 'merchantproduct', ['name_norm'])
    op.create_index('ix_merchantproduct_ean', 'merchantproduct', ['ean'])
    op.create_index('ix_merchantproduct_upc', 'merchantproduct', ['upc'])


def downgrade() -> None:
    op.drop_index('ix_merchantproduct_upc', table_name='merchantproduct')
    op.drop_index('ix_merchantproduct_ean', table_name='merchantproduct')
    op.drop_index('ix_merchantproduct_name_norm', table_name='merchantproduct')
    op.drop_index('ix_merchantproduct_merchant_id', table_name='merchantproduct')
    op.drop_table('merchantproduct')
