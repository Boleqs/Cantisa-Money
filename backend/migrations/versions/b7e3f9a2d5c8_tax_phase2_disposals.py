"""tax phase 2: asset disposals (realized capital gains)

Revision ID: b7e3f9a2d5c8
Revises: d4a9f2c6e1b8
Create Date: 2026-07-25 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b7e3f9a2d5c8'
down_revision: Union[str, Sequence[str], None] = 'd4a9f2c6e1b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'asset_disposal',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('possession_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('sale_price', sa.Numeric(), nullable=True),
        sa.Column('sale_price_native', sa.Numeric(), nullable=True),
        sa.Column('sale_date', sa.DateTime(), nullable=False),
        sa.Column('dest_account_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('tx_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('source_split_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('dest_split_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('realized_gain', sa.Numeric(), nullable=True),
        sa.Column('holding_period_days', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['possession_id'], ['asset_possession.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['dest_account_id'], ['accounts.id'], ondelete='SET NULL', onupdate='CASCADE'),
        sa.ForeignKeyConstraint(['tx_id'], ['transactions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['source_split_id'], ['splits.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['dest_split_id'], ['splits.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_check_constraint(
        'ck_asset_disposal_quantity',
        'asset_disposal',
        'quantity <= 1000000000 AND quantity >= 0',
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('ck_asset_disposal_quantity', 'asset_disposal', type_='check')
    op.drop_table('asset_disposal')
