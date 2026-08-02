"""add loan equity subtype

Revision ID: a3c7e4f1b829
Revises: e8f6b41d2865
Create Date: 2026-08-02 00:00:00.000000

Élargit le CheckConstraint account_subtype pour autoriser 'loan' sur un compte Equity — le
compte d'ouverture d'un crédit "déjà en cours" (is_existing_loan=True) est désormais auto-généré
par rt_loans.py plutôt que choisi manuellement par l'utilisateur parmi ses comptes Equity
existants, voir Accounts.vue (exclu de la liste des comptes, comme Liability) et
LoanModal.vue (select "Compte d'ouverture" supprimé).
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'a3c7e4f1b829'
down_revision: Union[str, Sequence[str], None] = 'e8f6b41d2865'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_constraint('accounts_check', 'accounts', type_='check')
    op.create_check_constraint(
        'accounts_check', 'accounts',
        "(account_type = 'Equity' AND account_subtype IN ('fr_PEA', 'Other', 'loan')) "
        "OR account_subtype IS NULL")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('accounts_check', 'accounts', type_='check')
    op.create_check_constraint(
        'accounts_check', 'accounts',
        "(account_type = 'Equity' AND account_subtype IN ('fr_PEA', 'Other')) "
        "OR account_subtype IS NULL")
