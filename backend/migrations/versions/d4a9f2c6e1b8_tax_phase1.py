"""tax phase 1: regimes, household profile, category tax-line

Revision ID: d4a9f2c6e1b8
Revises: b1e5c9d3a7f2
Create Date: 2026-07-24 22:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'd4a9f2c6e1b8'
down_revision: Union[str, Sequence[str], None] = 'b1e5c9d3a7f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'tax_regime',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('country_code', sa.String(2), nullable=False),
        sa.Column('tax_year', sa.Integer(), nullable=False),
        sa.Column('config', postgresql.JSONB(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('is_verified', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'name'),
    )

    op.create_table(
        'tax_household_profile',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tax_year', sa.Integer(), nullable=False),
        sa.Column('adults', sa.Integer(), nullable=False),
        sa.Column('dependents', sa.Integer(), nullable=False),
        sa.Column('dependents_disabled', sa.Integer(), nullable=False),
        sa.Column('parent_isole', sa.Boolean(), nullable=False),
        sa.Column('notes', sa.String(1000), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'tax_year'),
    )

    op.create_table(
        'tax_household_income',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('household_profile_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('label', sa.String(200), nullable=False),
        sa.Column('amount', sa.Numeric(), nullable=False),
        sa.Column('income_type', sa.String(32), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['household_profile_id'], ['tax_household_profile.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.add_column('categories', sa.Column('tax_treatment', sa.String(32), nullable=True))
    op.create_check_constraint(
        'ck_categories_tax_treatment',
        'categories',
        "tax_treatment IN ('taxable_income','deductible','real_estate_income','real_estate_expense') "
        "OR tax_treatment IS NULL",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('ck_categories_tax_treatment', 'categories', type_='check')
    op.drop_column('categories', 'tax_treatment')
    op.drop_table('tax_household_income')
    op.drop_table('tax_household_profile')
    op.drop_table('tax_regime')
