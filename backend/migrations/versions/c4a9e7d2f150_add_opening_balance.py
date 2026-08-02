"""add opening balance

Revision ID: c4a9e7d2f150
Revises: b8d1f2a94c6e
Create Date: 2026-08-02 05:00:00.000000

Ajoute la prise en charge d'un solde initial de reprise sur un compte (cas d'un compte intégré
à l'app dont l'historique de transactions a été perdu) : colonne
accounts.opening_balance_transaction_id référençant la transaction d'équilibrage générée, et
subtype Equity 'opening_balance' pour le compte de contrepartie partagé par devise (auto-généré
par rt_accounts.py, jamais sélectionnable manuellement — même logique que le subtype 'loan').
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c4a9e7d2f150'
down_revision: Union[str, Sequence[str], None] = 'b8d1f2a94c6e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'accounts',
        sa.Column('opening_balance_transaction_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        'accounts_opening_balance_transaction_id_fkey', 'accounts', 'transactions',
        ['opening_balance_transaction_id'], ['id'], ondelete='SET NULL', onupdate='CASCADE')

    op.drop_constraint('accounts_check', 'accounts', type_='check')
    op.create_check_constraint(
        'accounts_check', 'accounts',
        "(account_type = 'Equity' AND account_subtype IN ('fr_PEA', 'Other', 'loan', 'opening_balance')) "
        "OR account_subtype IS NULL")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('accounts_check', 'accounts', type_='check')
    op.create_check_constraint(
        'accounts_check', 'accounts',
        "(account_type = 'Equity' AND account_subtype IN ('fr_PEA', 'Other', 'loan')) "
        "OR account_subtype IS NULL")

    op.drop_constraint('accounts_opening_balance_transaction_id_fkey', 'accounts', type_='foreignkey')
    op.drop_column('accounts', 'opening_balance_transaction_id')
