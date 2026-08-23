"""add asset operations (split, merger, spinoff)

Revision ID: fb3f834c0962
Revises: 9c1e5a7f2b48
Create Date: 2026-08-23 19:00:00.000000

Opérations sur titre décidées par l'émetteur (split/regroupement, fusion, scission) : nouvelle
table asset_operations + colonne operation_id (traçabilité) sur asset_possession et asset_disposal
pour les lots/cessions créés automatiquement par une fusion/scission. Voir
backend/routes/rt_assets.py::create_asset_operation et backend/utils/portfolio_ops.py::cost_basis_per_unit.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'fb3f834c0962'
down_revision: Union[str, Sequence[str], None] = '9c1e5a7f2b48'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'asset_operations',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('asset_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('operation_type', sa.String(length=20), nullable=False),
        sa.Column('operation_date', sa.Date(), nullable=False),
        sa.Column('ratio_from', sa.Numeric(), nullable=False),
        sa.Column('ratio_to', sa.Numeric(), nullable=False),
        sa.Column('target_asset_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('cost_allocation_pct', sa.Numeric(), nullable=True),
        sa.Column('note', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['target_asset_id'], ['assets.id'], ondelete='SET NULL'),
        sa.CheckConstraint("operation_type IN ('split', 'merger', 'spinoff')", name='ck_asset_operations_type'),
        sa.CheckConstraint("ratio_from > 0 AND ratio_to > 0", name='ck_asset_operations_ratio'),
        sa.CheckConstraint(
            "cost_allocation_pct IS NULL OR (cost_allocation_pct >= 0 AND cost_allocation_pct <= 100)",
            name='ck_asset_operations_cost_allocation_pct'),
    )

    op.add_column('asset_possession', sa.Column('operation_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        'fk_asset_possession_operation_id', 'asset_possession', 'asset_operations',
        ['operation_id'], ['id'], ondelete='SET NULL')

    op.add_column('asset_disposal', sa.Column('operation_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        'fk_asset_disposal_operation_id', 'asset_disposal', 'asset_operations',
        ['operation_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_asset_disposal_operation_id', 'asset_disposal', type_='foreignkey')
    op.drop_column('asset_disposal', 'operation_id')

    op.drop_constraint('fk_asset_possession_operation_id', 'asset_possession', type_='foreignkey')
    op.drop_column('asset_possession', 'operation_id')

    op.drop_table('asset_operations')
