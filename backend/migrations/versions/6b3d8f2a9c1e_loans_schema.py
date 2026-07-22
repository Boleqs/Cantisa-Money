"""loans schema

Revision ID: 6b3d8f2a9c1e
Revises: e4a7c1f9b2d3
Create Date: 2026-07-22 10:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '6b3d8f2a9c1e'
down_revision: Union[str, Sequence[str], None] = 'e4a7c1f9b2d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'loans',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(length=128), nullable=False),
        sa.Column('principal', sa.Numeric(), nullable=False),
        sa.Column('annual_rate', sa.Numeric(), nullable=False),
        sa.Column('term_months', sa.Integer(), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=False),
        sa.Column('payment_day', sa.SmallInteger(), nullable=False),
        sa.Column('payment_account_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('interest_expense_account_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('insurance_expense_account_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('insurance_monthly_amount', sa.Numeric(), nullable=True),
        sa.Column('liability_account_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('equity_opening_account_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('opening_transaction_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('category_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('auto_debit', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_existing_loan', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_closed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('closed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.CheckConstraint("(is_existing_loan = false) OR (equity_opening_account_id IS NOT NULL)"),
        sa.CheckConstraint("principal > 0"),
        sa.CheckConstraint("annual_rate >= 0"),
        sa.CheckConstraint("term_months >= 1"),
        sa.CheckConstraint("payment_day BETWEEN 1 AND 31"),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['payment_account_id'], ['accounts.id'], ondelete='RESTRICT', onupdate='CASCADE'),
        sa.ForeignKeyConstraint(['interest_expense_account_id'], ['accounts.id'], ondelete='RESTRICT', onupdate='CASCADE'),
        sa.ForeignKeyConstraint(['insurance_expense_account_id'], ['accounts.id'], ondelete='RESTRICT', onupdate='CASCADE'),
        sa.ForeignKeyConstraint(['liability_account_id'], ['accounts.id'], ondelete='RESTRICT', onupdate='CASCADE'),
        sa.ForeignKeyConstraint(['equity_opening_account_id'], ['accounts.id'], ondelete='RESTRICT', onupdate='CASCADE'),
        sa.ForeignKeyConstraint(['opening_transaction_id'], ['transactions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['category_id'], ['categories.id'], ondelete='SET NULL', onupdate='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'name'),
    )

    op.create_table(
        'loan_rate_revisions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('loan_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('effective_date', sa.Date(), nullable=False),
        sa.Column('new_annual_rate', sa.Numeric(), nullable=False),
        sa.Column('recalc_mode', sa.String(length=16), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.CheckConstraint("recalc_mode IN ('keep_term', 'keep_payment')"),
        sa.ForeignKeyConstraint(['loan_id'], ['loans.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'loan_installments',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('loan_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('installment_number', sa.Integer(), nullable=False),
        sa.Column('due_date', sa.Date(), nullable=False),
        sa.Column('principal_portion', sa.Numeric(), nullable=False),
        sa.Column('interest_portion', sa.Numeric(), nullable=False),
        sa.Column('insurance_portion', sa.Numeric(), nullable=False, server_default='0'),
        sa.Column('total_amount', sa.Numeric(), nullable=False),
        sa.Column('remaining_principal_after', sa.Numeric(), nullable=False),
        sa.Column('is_paid', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('paid_at', sa.DateTime(), nullable=True),
        sa.Column('transaction_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('rate_revision_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['loan_id'], ['loans.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['transaction_id'], ['transactions.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['rate_revision_id'], ['loan_rate_revisions.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('loan_id', 'installment_number'),
    )
    op.create_index('ix_loan_installments_loan_due', 'loan_installments', ['loan_id', 'due_date'])
    op.create_index('ix_loan_installments_loan_paid', 'loan_installments', ['loan_id', 'is_paid'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_loan_installments_loan_paid', table_name='loan_installments')
    op.drop_index('ix_loan_installments_loan_due', table_name='loan_installments')
    op.drop_table('loan_installments')
    op.drop_table('loan_rate_revisions')
    op.drop_table('loans')
