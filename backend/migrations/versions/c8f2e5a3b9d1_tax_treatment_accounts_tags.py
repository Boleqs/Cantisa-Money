"""tax treatment on accounts and tags

Revision ID: c8f2e5a3b9d1
Revises: b7e3f9a2d5c8
Create Date: 2026-07-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c8f2e5a3b9d1'
down_revision: Union[str, Sequence[str], None] = 'b7e3f9a2d5c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('accounts', sa.Column('tax_treatment', sa.String(32), nullable=True))
    op.create_check_constraint(
        'ck_accounts_tax_treatment',
        'accounts',
        "tax_treatment IN ('taxable_income','deductible','real_estate_income','real_estate_expense') "
        "OR tax_treatment IS NULL",
    )

    op.add_column('tags', sa.Column('tax_treatment', sa.String(32), nullable=True))
    op.create_check_constraint(
        'ck_tags_tax_treatment',
        'tags',
        "tax_treatment IN ('taxable_income','deductible','real_estate_income','real_estate_expense') "
        "OR tax_treatment IS NULL",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('ck_tags_tax_treatment', 'tags', type_='check')
    op.drop_column('tags', 'tax_treatment')

    op.drop_constraint('ck_accounts_tax_treatment', 'accounts', type_='check')
    op.drop_column('accounts', 'tax_treatment')
