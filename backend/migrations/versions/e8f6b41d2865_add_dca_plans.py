"""add dca plans

Revision ID: e8f6b41d2865
Revises: 870fbb76215a
Create Date: 2026-07-29 00:00:00.000000

Ajout de la fonctionnalité DCA (investissement programmé) : une table `dca_plans` (plan récurrent
d'achat d'un actif, même modèle de récurrence discriminée que `subscriptions`), un lien de
traçabilité `dca_plan_id` sur `asset_possession` (quel plan a créé quel lot), et l'élargissement de
`asset_possession.quantity` / `asset_disposal.quantity` d'Integer vers un type décimal pour
permettre les quantités fractionnées (ex: 2.29 parts d'ETF) qu'un montant fixe en euros implique.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'e8f6b41d2865'
down_revision: Union[str, Sequence[str], None] = '870fbb76215a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint('asset_possession_quantity_check', 'asset_possession', type_='check')
    op.alter_column(
        'asset_possession', 'quantity',
        type_=sa.Numeric(18, 6), existing_type=sa.Integer(), nullable=False,
        postgresql_using='quantity::numeric(18,6)')
    op.create_check_constraint(
        'asset_possession_quantity_check', 'asset_possession',
        'quantity <= 1000000000 AND quantity >= 0')

    op.drop_constraint('ck_asset_disposal_quantity', 'asset_disposal', type_='check')
    op.alter_column(
        'asset_disposal', 'quantity',
        type_=sa.Numeric(18, 6), existing_type=sa.Integer(), nullable=False,
        postgresql_using='quantity::numeric(18,6)')
    op.create_check_constraint(
        'ck_asset_disposal_quantity', 'asset_disposal',
        'quantity <= 1000000000 AND quantity >= 0')

    op.create_table(
        'dca_plans',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=64), nullable=False),
        sa.Column('asset_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('source_account_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('dest_account_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('amount', sa.Numeric(), nullable=False, server_default='0'),
        sa.Column('schedule_type', sa.String(length=10), nullable=False, server_default='monthly'),
        sa.Column('day_of_month', sa.SmallInteger(), nullable=True),
        sa.Column('month_of_year', sa.SmallInteger(), nullable=True),
        sa.Column('weekdays', sa.String(length=20), nullable=True),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('is_forecast_only', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('last_executed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id', name='pk_dca_plans'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_dca_plans_user_id_users', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], name='fk_dca_plans_asset_id_assets', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['source_account_id'], ['accounts.id'], name='fk_dca_plans_source_account_id_accounts',
            ondelete='RESTRICT', onupdate='CASCADE'),
        sa.ForeignKeyConstraint(
            ['dest_account_id'], ['accounts.id'], name='fk_dca_plans_dest_account_id_accounts',
            ondelete='RESTRICT', onupdate='CASCADE'),
        sa.UniqueConstraint('user_id', 'name', name='uq_dca_plans_user_id_name'),
        sa.CheckConstraint("schedule_type IN ('monthly', 'yearly', 'weekly')", name='ck_dca_plans_schedule_type'),
    )

    op.add_column('asset_possession', sa.Column('dca_plan_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        'fk_asset_possession_dca_plan_id_dca_plans', 'asset_possession', 'dca_plans',
        ['dca_plan_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_asset_possession_dca_plan_id_dca_plans', 'asset_possession', type_='foreignkey')
    op.drop_column('asset_possession', 'dca_plan_id')

    op.drop_table('dca_plans')

    op.drop_constraint('ck_asset_disposal_quantity', 'asset_disposal', type_='check')
    op.alter_column(
        'asset_disposal', 'quantity',
        type_=sa.Integer(), existing_type=sa.Numeric(18, 6), nullable=False,
        postgresql_using='quantity::integer')
    op.create_check_constraint(
        'ck_asset_disposal_quantity', 'asset_disposal',
        'quantity <= 1000000000 AND quantity >= 0')

    op.drop_constraint('asset_possession_quantity_check', 'asset_possession', type_='check')
    op.alter_column(
        'asset_possession', 'quantity',
        type_=sa.Integer(), existing_type=sa.Numeric(18, 6), nullable=False,
        postgresql_using='quantity::integer')
    op.create_check_constraint(
        'asset_possession_quantity_check', 'asset_possession',
        'quantity <= 1000000000 AND quantity >= 0')
